#!/usr/bin/env python3
"""Dependency-free SMS Gateway MVP control plane.

The HTTP API accepts normalized Android events, persists them in SQLite, updates
the device registry, and serves a small local operations dashboard.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


VERSION = "0.1.0"
MAX_BODY_BYTES = 1024 * 1024
STATIC_DIR = Path(__file__).with_name("static")
UNKNOWN_CALL_TYPES = {"", "0", "unknown", "unknown call", "未知", "未知通话"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: Any, max_length: int = 4096) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).strip()[:max_length]


def first_value(payload: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def infer_event_type(payload: Dict[str, Any], call_type: str) -> str:
    requested = clean_text(first_value(payload, "event_type", "type"), 32).lower()
    if requested in {"sms", "call", "heartbeat", "test"}:
        return requested
    if call_type.lower() not in UNKNOWN_CALL_TYPES:
        return "call"
    return "sms"


def normalize_sim_slot(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = clean_text(value, 128)
    match = re.search(r"(?:sim|slot|卡槽)\s*([12])", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    try:
        number = int(text)
    except ValueError:
        return None
    if number == 0:
        return 1
    return number if number in (1, 2) else None


def normalize_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    call_type = clean_text(first_value(payload, "call_type", "callType"), 128)
    event_type = infer_event_type(payload, call_type)
    device_id = clean_text(
        first_value(payload, "device_id", "device_mark", "device", "deviceId"), 128
    )
    if not device_id:
        device_id = "unregistered-android"

    sender = clean_text(first_value(payload, "sender", "from", "phone", "mobile"), 256)
    content = clean_text(
        first_value(payload, "content", "message", "msg", "org_content"), 65535
    )
    received_at = clean_text(
        first_value(payload, "received_at", "receive_time", "receivedAt", "date"), 64
    ) or utc_now()
    sim_label = clean_text(first_value(payload, "sim", "sim_info", "card_slot", "title"), 128)
    sim_slot = normalize_sim_slot(first_value(payload, "sim_slot", "slot", "card_slot", "sim"))
    sub_id = clean_text(first_value(payload, "sub_id", "subscription_id", "card_subid"), 64)
    app_version = clean_text(first_value(payload, "app_version", "version"), 64)
    battery = clean_text(first_value(payload, "battery", "battery_info"), 256)
    network_type = clean_text(first_value(payload, "network", "network_type", "net_type"), 64)

    if event_type in {"sms", "call"} and not sender:
        raise ValueError("sender is required for sms and call events")
    if event_type == "sms" and not content:
        raise ValueError("content is required for sms events")

    stable = {
        "device_id": device_id,
        "event_type": event_type,
        "sender": sender,
        "content": content,
        "received_at": received_at,
        "sim_slot": sim_slot,
        "sub_id": sub_id,
        "call_type": call_type,
    }
    event_id = clean_text(first_value(payload, "event_id", "id"), 128)
    if not event_id:
        canonical = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        event_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return {
        **stable,
        "event_id": event_id,
        "sim_label": sim_label,
        "app_version": app_version,
        "battery": battery,
        "network_type": network_type,
        "raw_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
    }


class GatewayStore:
    def __init__(self, database_path: str):
        self.database_path = database_path
        self._lock = threading.RLock()
        database = Path(database_path)
        database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        schema = """
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            device_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            sender TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL,
            sim_slot INTEGER,
            sim_label TEXT NOT NULL DEFAULT '',
            sub_id TEXT NOT NULL DEFAULT '',
            call_type TEXT NOT NULL DEFAULT '',
            app_version TEXT NOT NULL DEFAULT '',
            battery TEXT NOT NULL DEFAULT '',
            network_type TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_received_at ON events(received_at DESC);
        CREATE INDEX IF NOT EXISTS idx_events_device_type ON events(device_id, event_type);
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            last_seen TEXT NOT NULL,
            app_version TEXT NOT NULL DEFAULT '',
            battery TEXT NOT NULL DEFAULT '',
            network_type TEXT NOT NULL DEFAULT '',
            sim_slot INTEGER,
            sim_label TEXT NOT NULL DEFAULT '',
            last_event_type TEXT NOT NULL DEFAULT '',
            last_sender TEXT NOT NULL DEFAULT ''
        );
        """
        with self._lock, self._connect() as connection:
            connection.executescript(schema)

    def insert_event(self, event: Dict[str, Any]) -> Tuple[bool, str]:
        created_at = utc_now()
        fields = (
            event["event_id"], event["device_id"], event["event_type"], event["sender"],
            event["content"], event["received_at"], event["sim_slot"], event["sim_label"],
            event["sub_id"], event["call_type"], event["app_version"], event["battery"],
            event["network_type"], event["raw_json"], created_at,
        )
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO events (
                    event_id, device_id, event_type, sender, content, received_at,
                    sim_slot, sim_label, sub_id, call_type, app_version, battery,
                    network_type, raw_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                fields,
            )
            inserted = cursor.rowcount == 1
            connection.execute(
                """INSERT INTO devices (
                    device_id, last_seen, app_version, battery, network_type,
                    sim_slot, sim_label, last_event_type, last_sender
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    last_seen=excluded.last_seen,
                    app_version=CASE WHEN excluded.app_version != '' THEN excluded.app_version ELSE devices.app_version END,
                    battery=CASE WHEN excluded.battery != '' THEN excluded.battery ELSE devices.battery END,
                    network_type=CASE WHEN excluded.network_type != '' THEN excluded.network_type ELSE devices.network_type END,
                    sim_slot=COALESCE(excluded.sim_slot, devices.sim_slot),
                    sim_label=CASE WHEN excluded.sim_label != '' THEN excluded.sim_label ELSE devices.sim_label END,
                    last_event_type=excluded.last_event_type,
                    last_sender=excluded.last_sender""",
                (
                    event["device_id"], created_at, event["app_version"], event["battery"],
                    event["network_type"], event["sim_slot"], event["sim_label"],
                    event["event_type"], event["sender"],
                ),
            )
        return inserted, event["event_id"]

    def list_events(self, limit: int = 100, event_type: str = "", device_id: str = "") -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if device_id:
            clauses.append("device_id = ?")
            params.append(device_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(max(1, min(limit, 500)))
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events" + where + " ORDER BY id DESC LIMIT ?", params
            ).fetchall()
        return [dict(row) for row in rows]

    def list_devices(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            counts = connection.execute(
                "SELECT event_type, COUNT(*) AS count FROM events GROUP BY event_type"
            ).fetchall()
            device_count = connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        return {"devices": device_count, "events": {row["event_type"]: row["count"] for row in counts}}


class GatewayRequestHandler(BaseHTTPRequestHandler):
    server_version = "SmsGatewayMVP/" + VERSION

    @property
    def gateway_server(self) -> "GatewayHTTPServer":
        return self.server  # type: ignore[return-value]

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - %s" % (self.log_date_time_string(), fmt % args), flush=True)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = self.gateway_server.gateway_token
        if not expected:
            return True
        provided = self.headers.get("X-Gateway-Token", "")
        if not provided:
            authorization = self.headers.get("Authorization", "")
            if authorization.lower().startswith("bearer "):
                provided = authorization[7:].strip()
        return bool(provided) and hmac.compare_digest(provided, expected)

    def _read_json(self) -> Dict[str, Any]:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise ValueError("Content-Length is required")
        length = int(content_length)
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body size is invalid")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path not in {"/api/v1/events", "/api/v1/devices/heartbeat"}:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        try:
            payload = self._read_json()
            if path.endswith("heartbeat"):
                payload["event_type"] = "heartbeat"
            event = normalize_event(payload)
            inserted, event_id = self.gateway_server.store.insert_event(event)
        except (ValueError, TypeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        self._json(
            HTTPStatus.CREATED if inserted else HTTPStatus.OK,
            {
                "ok": True,
                "code": "SMS_MVP_OK",
                "event_id": event_id,
                "duplicate": not inserted,
            },
        )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/health":
            self._json(HTTPStatus.OK, {"ok": True, "version": VERSION, **self.gateway_server.store.stats()})
            return
        if path == "/api/v1/events":
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                limit = 100
            events = self.gateway_server.store.list_events(
                limit=limit,
                event_type=clean_text(query.get("type", [""])[0], 32).lower(),
                device_id=clean_text(query.get("device_id", [""])[0], 128),
            )
            self._json(HTTPStatus.OK, {"ok": True, "events": events})
            return
        if path == "/api/v1/devices":
            self._json(HTTPStatus.OK, {"ok": True, "devices": self.gateway_server.store.list_devices()})
            return
        self._serve_static(path)

    def _serve_static(self, request_path: str) -> None:
        names = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        item = names.get(request_path)
        if not item:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        file_name, content_type = item
        body = (STATIC_DIR / file_name).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)


class GatewayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: Tuple[str, int], store: GatewayStore, gateway_token: str):
        super().__init__(address, GatewayRequestHandler)
        self.store = store
        self.gateway_token = gateway_token


def create_server(host: str, port: int, database_path: str, gateway_token: str) -> GatewayHTTPServer:
    return GatewayHTTPServer((host, port), GatewayStore(database_path), gateway_token)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SMS Gateway MVP server")
    parser.add_argument("--host", default=os.environ.get("SMS_GATEWAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SMS_GATEWAY_PORT", "8787")))
    parser.add_argument("--database", default=os.environ.get("SMS_GATEWAY_DB", "data/gateway.db"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.environ.get("GATEWAY_TOKEN", "").strip()
    if not token:
        raise SystemExit("GATEWAY_TOKEN must be set")
    server = create_server(args.host, args.port, args.database, token)
    print(
        "SMS Gateway MVP %s listening on http://%s:%s (db=%s)"
        % (VERSION, args.host, args.port, args.database),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
