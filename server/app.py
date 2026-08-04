#!/usr/bin/env python3
"""Dependency-free SMS Gateway MVP control plane.

The HTTP API accepts normalized Android events, persists them in SQLite, updates
the device registry, and serves a small local operations dashboard.
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


VERSION = "0.2.0"
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


def device_id_from_payload(payload: Dict[str, Any]) -> str:
    return clean_text(
        first_value(payload, "device_id", "device_mark", "device", "deviceId"), 128
    ) or "unregistered-android"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
    device_id = device_id_from_payload(payload)

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
            first_seen TEXT NOT NULL DEFAULT '',
            last_seen TEXT NOT NULL,
            last_heartbeat TEXT NOT NULL DEFAULT '',
            app_version TEXT NOT NULL DEFAULT '',
            battery TEXT NOT NULL DEFAULT '',
            network_type TEXT NOT NULL DEFAULT '',
            sim_slot INTEGER,
            sim_label TEXT NOT NULL DEFAULT '',
            last_event_type TEXT NOT NULL DEFAULT '',
            last_sender TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS device_credentials (
            device_id TEXT PRIMARY KEY,
            label TEXT NOT NULL DEFAULT '',
            token_hash TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_authenticated TEXT NOT NULL DEFAULT ''
        );
        """
        with self._lock, self._connect() as connection:
            connection.executescript(schema)
            self._ensure_column(connection, "devices", "first_seen", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "devices", "last_heartbeat", "TEXT NOT NULL DEFAULT ''")
            connection.execute("UPDATE devices SET first_seen = last_seen WHERE first_seen = ''")

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(%s)" % table)}
        if column not in columns:
            connection.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, definition))

    def ensure_device_credential(self, device_id: str, token: str, label: str = "") -> None:
        now = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO device_credentials (
                    device_id, label, token_hash, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?)""",
                (device_id, label, token_digest(token), now, now),
            )

    def provision_device(self, device_id: str, label: str = "") -> str:
        device_id = clean_text(device_id, 128)
        if not device_id:
            raise ValueError("device_id is required")
        token = secrets.token_urlsafe(32)
        now = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO device_credentials (
                    device_id, label, token_hash, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    label=excluded.label,
                    token_hash=excluded.token_hash,
                    enabled=1,
                    updated_at=excluded.updated_at""",
                (device_id, clean_text(label, 128), token_digest(token), now, now),
            )
        return token

    def authenticate_device(self, device_id: str, token: str) -> bool:
        if not device_id or not token:
            return False
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT token_hash, enabled FROM device_credentials WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if not row or row["enabled"] != 1:
                return False
            authenticated = hmac.compare_digest(token_digest(token), row["token_hash"])
            if authenticated:
                connection.execute(
                    "UPDATE device_credentials SET last_authenticated = ? WHERE device_id = ?",
                    (utc_now(), device_id),
                )
        return authenticated

    def credential_count(self) -> int:
        with self._lock, self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM device_credentials").fetchone()[0])

    def list_device_credentials(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT c.device_id, c.label, c.enabled, c.created_at, c.updated_at,
                          c.last_authenticated, d.last_seen, d.last_heartbeat
                   FROM device_credentials c
                   LEFT JOIN devices d ON d.device_id = c.device_id
                   ORDER BY c.device_id"""
            ).fetchall()
        return [dict(row) for row in rows]

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
                    device_id, first_seen, last_seen, app_version, battery, network_type,
                    sim_slot, sim_label, last_event_type, last_sender
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    event["device_id"], created_at, created_at, event["app_version"], event["battery"],
                    event["network_type"], event["sim_slot"], event["sim_label"],
                    event["event_type"], event["sender"],
                ),
            )
        return inserted, event["event_id"]

    def record_heartbeat(self, payload: Dict[str, Any]) -> str:
        device_id = device_id_from_payload(payload)
        if device_id == "unregistered-android":
            raise ValueError("device_id is required")
        now = utc_now()
        app_version = clean_text(first_value(payload, "app_version", "version"), 64)
        battery = clean_text(first_value(payload, "battery", "battery_info"), 256)
        network_type = clean_text(first_value(payload, "network", "network_type", "net_type"), 64)
        sim_label = clean_text(first_value(payload, "sim", "sim_info", "card_slot", "title"), 128)
        sim_slot = normalize_sim_slot(first_value(payload, "sim_slot", "slot", "card_slot", "sim"))
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO devices (
                    device_id, first_seen, last_seen, last_heartbeat, app_version,
                    battery, network_type, sim_slot, sim_label, last_event_type, last_sender
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'heartbeat', '')
                ON CONFLICT(device_id) DO UPDATE SET
                    last_seen=excluded.last_seen,
                    last_heartbeat=excluded.last_heartbeat,
                    app_version=CASE WHEN excluded.app_version != '' THEN excluded.app_version ELSE devices.app_version END,
                    battery=CASE WHEN excluded.battery != '' THEN excluded.battery ELSE devices.battery END,
                    network_type=CASE WHEN excluded.network_type != '' THEN excluded.network_type ELSE devices.network_type END,
                    sim_slot=COALESCE(excluded.sim_slot, devices.sim_slot),
                    sim_label=CASE WHEN excluded.sim_label != '' THEN excluded.sim_label ELSE devices.sim_label END""",
                (device_id, now, now, now, app_version, battery, network_type, sim_slot, sim_label),
            )
        return now

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

    def list_devices(self, offline_seconds: int = 180) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
        now = datetime.now(timezone.utc)
        devices = []
        for row in rows:
            device = dict(row)
            try:
                last_seen = datetime.fromisoformat(device["last_seen"])
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                seconds = max(0, int((now - last_seen).total_seconds()))
            except (TypeError, ValueError):
                seconds = offline_seconds + 1
            device["seconds_since_seen"] = seconds
            device["online"] = seconds <= offline_seconds
            devices.append(device)
        return devices

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
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'",
        )
        self.send_header("Cache-Control", "no-store")

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _provided_token(self) -> str:
        provided = self.headers.get("X-Gateway-Token", "")
        if not provided:
            authorization = self.headers.get("Authorization", "")
            if authorization.lower().startswith("bearer "):
                provided = authorization[7:].strip()
        return provided

    def _device_authorized(self, payload: Dict[str, Any]) -> bool:
        provided = self._provided_token()
        device_id = device_id_from_payload(payload)
        if self.gateway_server.store.authenticate_device(device_id, provided):
            return True
        expected = self.gateway_server.legacy_gateway_token
        return (
            self.gateway_server.store.credential_count() == 0
            and bool(expected)
            and bool(provided)
            and hmac.compare_digest(provided, expected)
        )

    def _admin_authorized(self) -> bool:
        expected_user = self.gateway_server.admin_username
        expected_password = self.gateway_server.admin_password
        if not expected_user and not expected_password:
            return True
        authorization = self.headers.get("Authorization", "")
        if not authorization.lower().startswith("basic "):
            return False
        try:
            decoded = base64.b64decode(authorization[6:].strip(), validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return False
        return hmac.compare_digest(username, expected_user) and hmac.compare_digest(
            password, expected_password
        )

    def _admin_unauthorized(self) -> None:
        body = json.dumps({"ok": False, "error": "admin authentication required"}).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="SMS Gateway Admin", charset="UTF-8"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

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
        if path == "/api/v1/admin/devices" or (
            path.startswith("/api/v1/admin/devices/") and path.endswith("/rotate")
        ):
            if not self._admin_authorized():
                self._admin_unauthorized()
                return
            try:
                payload = self._read_json()
                if path.endswith("/rotate"):
                    device_id = path[len("/api/v1/admin/devices/") : -len("/rotate")].strip("/")
                else:
                    device_id = clean_text(payload.get("device_id"), 128)
                token = self.gateway_server.store.provision_device(
                    device_id, clean_text(payload.get("label"), 128)
                )
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(
                HTTPStatus.CREATED,
                {"ok": True, "device_id": device_id, "token": token, "token_shown_once": True},
            )
            return
        if path not in {"/api/v1/events", "/api/v1/devices/heartbeat"}:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        try:
            payload = self._read_json()
            if not self._device_authorized(payload):
                self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized device"})
                return
            if path.endswith("heartbeat"):
                heartbeat_at = self.gateway_server.store.record_heartbeat(payload)
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "code": "SMS_MVP_OK",
                        "heartbeat_at": heartbeat_at,
                        "next_heartbeat_seconds": self.gateway_server.heartbeat_seconds,
                    },
                )
                return
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
        if not self._admin_authorized():
            self._admin_unauthorized()
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
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "offline_seconds": self.gateway_server.offline_seconds,
                    "devices": self.gateway_server.store.list_devices(self.gateway_server.offline_seconds),
                },
            )
            return
        if path == "/api/v1/admin/devices":
            self._json(
                HTTPStatus.OK,
                {"ok": True, "credentials": self.gateway_server.store.list_device_credentials()},
            )
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

    def __init__(
        self,
        address: Tuple[str, int],
        store: GatewayStore,
        gateway_token: str,
        admin_username: str = "",
        admin_password: str = "",
        bootstrap_device_id: str = "",
        offline_seconds: int = 180,
        heartbeat_seconds: int = 300,
    ):
        super().__init__(address, GatewayRequestHandler)
        self.store = store
        self.legacy_gateway_token = gateway_token
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.offline_seconds = max(30, offline_seconds)
        self.heartbeat_seconds = max(60, heartbeat_seconds)
        if bootstrap_device_id and gateway_token:
            self.store.ensure_device_credential(bootstrap_device_id, gateway_token, bootstrap_device_id)


def create_server(
    host: str,
    port: int,
    database_path: str,
    gateway_token: str,
    admin_username: str = "",
    admin_password: str = "",
    bootstrap_device_id: str = "",
    offline_seconds: int = 180,
    heartbeat_seconds: int = 300,
) -> GatewayHTTPServer:
    return GatewayHTTPServer(
        (host, port),
        GatewayStore(database_path),
        gateway_token,
        admin_username,
        admin_password,
        bootstrap_device_id,
        offline_seconds,
        heartbeat_seconds,
    )


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
    admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and (
        not admin_username or not admin_password
    ):
        raise SystemExit("ADMIN_USERNAME and ADMIN_PASSWORD must be set on non-loopback hosts")
    server = create_server(
        args.host,
        args.port,
        args.database,
        token,
        admin_username,
        admin_password,
        os.environ.get("SMS_GATEWAY_BOOTSTRAP_DEVICE_ID", "").strip(),
        int(os.environ.get("DEVICE_OFFLINE_SECONDS", "180")),
        int(os.environ.get("DEVICE_HEARTBEAT_SECONDS", "300")),
    )
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
