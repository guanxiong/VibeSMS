#!/usr/bin/env python3
"""Dependency-free VibeSMS control plane.

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
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


VERSION = "0.12.0"
PRODUCT_NAME = "VibeSMS"
MAX_BODY_BYTES = 1024 * 1024
STATIC_DIR = Path(__file__).with_name("static")
UNKNOWN_CALL_TYPES = {"", "0", "unknown", "unknown call", "未知", "未知通话"}
USER_KEY_PREFIX = "vbs_live_"
ACTIVATION_CODE_PREFIX = "vba_"
REQUEST_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ATTRIBUTION_VALUE_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
CLAIM_DEVICE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")
CAMPAIGN_SOURCES = {"v2ex", "x", "github", "skills-sh", "hacker-news", "reddit", "wechat", "other"}
CAMPAIGN_LANDINGS = {"home", "apply"}
FEISHU_WEBHOOK_HOSTS = {"open.feishu.cn", "open.larksuite.com"}


class ConflictError(ValueError):
    """The request is valid but conflicts with an existing active binding."""


class ActivationError(ValueError):
    """An activation code is invalid, expired, or has already been used."""


class WebhookDeliveryError(ValueError):
    """A configured webhook rejected or returned an invalid response."""


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


def claim_device_digest(value: Any) -> str:
    claim_device_id = clean_text(value, 128)
    if not claim_device_id:
        return ""
    if not CLAIM_DEVICE_PATTERN.fullmatch(claim_device_id):
        raise ValueError("claim_device_id is invalid")
    return token_digest("vibesms-claim-device:" + claim_device_id)


def normalize_phone_number(value: Any) -> str:
    phone_number = re.sub(r"[\s()-]", "", clean_text(value, 32))
    if not re.fullmatch(r"\+?[0-9]{5,20}", phone_number):
        raise ValueError("phone_number must contain 5 to 20 digits with an optional leading +")
    return phone_number


def normalize_attribution(value: Any, allowed: set[str], fallback: str) -> str:
    normalized = clean_text(value, 64).lower()
    if not normalized:
        return fallback
    if not ATTRIBUTION_VALUE_PATTERN.fullmatch(normalized) or normalized not in allowed:
        return fallback
    return normalized


def normalize_webhook_keywords(value: Any) -> List[str]:
    if isinstance(value, str):
        values = re.split(r"[,，\n]", value)
    elif isinstance(value, list):
        values = value
    else:
        values = []
    keywords: List[str] = []
    for item in values:
        keyword = clean_text(item, 40)
        if keyword and keyword.casefold() not in {current.casefold() for current in keywords}:
            keywords.append(keyword)
    if not keywords:
        raise ValueError("at least one keyword is required")
    if len(keywords) > 10:
        raise ValueError("no more than 10 keywords are allowed")
    return keywords


def validate_feishu_webhook_url(value: Any) -> str:
    webhook_url = clean_text(value, 1024)
    parsed = urlparse(webhook_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in FEISHU_WEBHOOK_HOSTS
        or not re.fullmatch(r"/open-apis/bot/v2/hook/[A-Za-z0-9_-]{16,256}", parsed.path)
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("please provide a valid Feishu or Lark custom bot webhook URL")
    return webhook_url


def extract_otp(content: str) -> str:
    candidates: List[Tuple[int, int, str]] = []
    for match in re.finditer(r"(?<!\d)(\d(?:[ -]?\d){3,7})(?!\d)", content):
        code = re.sub(r"\D", "", match.group(1))
        if 4 <= len(code) <= 8:
            context = content[max(0, match.start() - 32) : match.end() + 32].lower()
            score = 10 if re.search(r"code|otp|verification|验证码|校验码|动态码", context) else 0
            if len(code) == 6:
                score += 3
            elif len(code) in (4, 8):
                score += 1
            if len(code) == 4 and 1900 <= int(code) <= 2099:
                score -= 4
            candidates.append((score, -match.start(), code))
    return max(candidates)[2] if candidates else ""


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


def api_sim_slot(value: Any) -> Optional[int]:
    if value is None or clean_text(value, 16) == "":
        return None
    try:
        sim_slot = int(clean_text(value, 16))
    except ValueError as exc:
        raise ValueError("sim_slot must be 1 or 2") from exc
    if sim_slot not in (1, 2):
        raise ValueError("sim_slot must be 1 or 2")
    return sim_slot


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
        CREATE TABLE IF NOT EXISTS user_keys (
            key_id TEXT PRIMARY KEY,
            label TEXT NOT NULL DEFAULT '',
            phone_number TEXT NOT NULL,
            owner_ref TEXT NOT NULL DEFAULT '',
            device_id TEXT NOT NULL DEFAULT '',
            sim_slot INTEGER,
            token_hash TEXT NOT NULL UNIQUE,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_accessed TEXT NOT NULL DEFAULT '',
            CHECK (sim_slot IS NULL OR sim_slot IN (1, 2))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_keys_active_phone
            ON user_keys(phone_number) WHERE enabled = 1;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_keys_active_binding
            ON user_keys(device_id, sim_slot)
            WHERE enabled = 1 AND device_id != '' AND sim_slot IS NOT NULL;
        CREATE TABLE IF NOT EXISTS key_requests (
            request_id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            phone_number TEXT NOT NULL DEFAULT '',
            contact TEXT NOT NULL DEFAULT '',
            use_case TEXT NOT NULL,
            device_count TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            activation_id TEXT NOT NULL DEFAULT '',
            key_id TEXT NOT NULL DEFAULT '',
            attribution_source TEXT NOT NULL DEFAULT 'direct',
            attribution_campaign TEXT NOT NULL DEFAULT 'none',
            attribution_landing TEXT NOT NULL DEFAULT 'apply',
            claim_device_hash TEXT NOT NULL DEFAULT '',
            review_reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_key_requests_status ON key_requests(status, created_at DESC);
        CREATE TABLE IF NOT EXISTS campaigns (
            campaign_id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            landing TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (landing IN ('home', 'apply'))
        );
        CREATE INDEX IF NOT EXISTS idx_campaigns_enabled ON campaigns(enabled, created_at DESC);
        CREATE TABLE IF NOT EXISTS key_milestones (
            key_id TEXT PRIMARY KEY,
            bound_at TEXT NOT NULL DEFAULT '',
            first_heartbeat_at TEXT NOT NULL DEFAULT '',
            first_event_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(key_id) REFERENCES user_keys(key_id)
        );
        CREATE TABLE IF NOT EXISTS activation_codes (
            activation_id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            code_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'available',
            expires_at TEXT NOT NULL,
            redeemed_at TEXT NOT NULL DEFAULT '',
            redeemed_phone TEXT NOT NULL DEFAULT '',
            key_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_activation_codes_status
            ON activation_codes(status, created_at DESC);
        CREATE TABLE IF NOT EXISTS onboarding_settings (
            settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
            auto_issue_enabled INTEGER NOT NULL DEFAULT 0,
            auto_issue_quota INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS webhook_configs (
            webhook_id TEXT PRIMARY KEY,
            key_id TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL DEFAULT 'feishu',
            webhook_url TEXT NOT NULL,
            keywords_json TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_tested_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(key_id) REFERENCES user_keys(key_id),
            CHECK (provider = 'feishu')
        );
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            response_code INTEGER,
            last_error TEXT NOT NULL DEFAULT '',
            next_attempt_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sent_at TEXT NOT NULL DEFAULT '',
            UNIQUE(webhook_id, event_id),
            FOREIGN KEY(webhook_id) REFERENCES webhook_configs(webhook_id)
        );
        CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_due
            ON webhook_deliveries(status, next_attempt_at, delivery_id);
        """
        with self._lock, self._connect() as connection:
            connection.executescript(schema)
            self._ensure_column(connection, "devices", "first_seen", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "devices", "last_heartbeat", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "key_requests", "phone_number", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "key_requests", "key_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "key_requests", "attribution_source", "TEXT NOT NULL DEFAULT 'direct'")
            self._ensure_column(connection, "key_requests", "attribution_campaign", "TEXT NOT NULL DEFAULT 'none'")
            self._ensure_column(connection, "key_requests", "attribution_landing", "TEXT NOT NULL DEFAULT 'apply'")
            self._ensure_column(connection, "key_requests", "claim_device_hash", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "key_requests", "review_reason", "TEXT NOT NULL DEFAULT ''")
            connection.execute(
                """CREATE INDEX IF NOT EXISTS idx_key_requests_attribution
                   ON key_requests(attribution_source, attribution_campaign, created_at DESC)"""
            )
            connection.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_key_requests_auto_issue_device
                   ON key_requests(claim_device_hash)
                   WHERE status = 'auto_issued' AND claim_device_hash != ''"""
            )
            connection.execute("UPDATE devices SET first_seen = last_seen WHERE first_seen = ''")
            connection.execute(
                """UPDATE webhook_deliveries
                   SET status = 'failed', last_error = 'delivery interrupted by restart',
                       next_attempt_at = ?, updated_at = ?
                   WHERE status = 'sending'""",
                (utc_now(), utc_now()),
            )
            connection.execute(
                """INSERT OR IGNORE INTO onboarding_settings (
                    settings_id, auto_issue_enabled, auto_issue_quota, updated_at
                ) VALUES (1, 0, 0, ?)""",
                (utc_now(),),
            )

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

    @staticmethod
    def _new_user_token() -> str:
        return USER_KEY_PREFIX + secrets.token_urlsafe(32)

    @staticmethod
    def _new_key_id() -> str:
        return "vk_" + secrets.token_hex(8)

    @staticmethod
    def _new_activation_id() -> str:
        return "va_" + secrets.token_hex(8)

    @staticmethod
    def _new_request_id() -> str:
        return "vr_" + secrets.token_hex(8)

    @staticmethod
    def _new_campaign_id() -> str:
        return "vc_" + secrets.token_hex(8)

    @staticmethod
    def _new_activation_code() -> str:
        return ACTIVATION_CODE_PREFIX + secrets.token_urlsafe(24)

    def create_campaign(self, name: str, code: str, source: str, landing: str) -> Dict[str, Any]:
        name = clean_text(name, 128)
        code = clean_text(code, 64).lower()
        source = normalize_attribution(source, CAMPAIGN_SOURCES, "")
        landing = normalize_attribution(landing, CAMPAIGN_LANDINGS, "")
        if not name:
            raise ValueError("campaign name is required")
        if not ATTRIBUTION_VALUE_PATTERN.fullmatch(code):
            raise ValueError("campaign code must use lowercase letters, numbers, dots, underscores, or hyphens")
        if not source:
            raise ValueError("campaign source is invalid")
        if not landing:
            raise ValueError("campaign landing must be home or apply")
        campaign = {
            "campaign_id": self._new_campaign_id(), "code": code, "name": name,
            "source": source, "landing": landing, "enabled": True,
            "created_at": utc_now(), "updated_at": utc_now(),
        }
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """INSERT INTO campaigns (
                        campaign_id, code, name, source, landing, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (
                        campaign["campaign_id"], campaign["code"], campaign["name"],
                        campaign["source"], campaign["landing"], campaign["created_at"],
                        campaign["updated_at"],
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictError("campaign code already exists") from exc
        return campaign

    def list_campaigns(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT campaign_id, code, name, source, landing, enabled, created_at, updated_at
                   FROM campaigns ORDER BY created_at DESC"""
            ).fetchall()
        campaigns = []
        for row in rows:
            campaign = dict(row)
            campaign["enabled"] = bool(campaign["enabled"])
            campaigns.append(campaign)
        return campaigns

    def set_campaign_enabled(self, campaign_id: str, enabled: bool) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE campaigns SET enabled = ?, updated_at = ? WHERE campaign_id = ?""",
                (1 if enabled else 0, utc_now(), clean_text(campaign_id, 64)),
            )
            if cursor.rowcount != 1:
                raise ValueError("campaign not found")

    def resolve_campaign(self, code: Any, landing: Any) -> Tuple[str, str, str]:
        code = clean_text(code, 64).lower()
        landing = normalize_attribution(landing, CAMPAIGN_LANDINGS, "apply")
        if not code or not ATTRIBUTION_VALUE_PATTERN.fullmatch(code):
            return "direct", "none", landing
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT code, source, landing FROM campaigns
                   WHERE code = ? AND enabled = 1""",
                (code,),
            ).fetchone()
        if not row or row["landing"] != landing:
            return "direct", "none", landing
        return row["source"], row["code"], row["landing"]

    def submit_key_request(
        self,
        email: str,
        use_case: str,
        device_count: str,
        contact: str = "",
        phone_number: str = "",
        attribution_campaign: str = "",
        attribution_landing: str = "apply",
        claim_device_id: str = "",
    ) -> Dict[str, Any]:
        email = clean_text(email, 254).lower()
        use_case = clean_text(use_case, 600)
        contact = clean_text(contact, 256)
        device_count = clean_text(device_count, 16)
        if not REQUEST_EMAIL_PATTERN.fullmatch(email):
            raise ValueError("please provide a valid email address")
        if len(use_case) < 2:
            raise ValueError("please briefly describe the intended use")
        if device_count not in {"1", "2-5", "6+"}:
            raise ValueError("device_count must be 1, 2-5, or 6+")
        phone_number = normalize_phone_number(phone_number)
        claim_device_hash = claim_device_digest(claim_device_id)
        attribution_source, attribution_campaign, attribution_landing = self.resolve_campaign(
            attribution_campaign, attribution_landing
        )
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat(timespec="seconds")
        recent_threshold = (now_dt - timedelta(days=1)).isoformat(timespec="seconds")
        request_id = self._new_request_id()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            recent = connection.execute(
                """SELECT COUNT(*) FROM key_requests
                   WHERE email = ? AND created_at >= ?""",
                (email, recent_threshold),
            ).fetchone()[0]
            if recent >= 3:
                raise ConflictError("too many requests for this email; please try again tomorrow")
            active_for_email = connection.execute(
                """SELECT 1 FROM key_requests r
                   JOIN user_keys k ON k.owner_ref = ('request:' || r.request_id)
                   WHERE r.email = ? AND k.enabled = 1 LIMIT 1""",
                (email,),
            ).fetchone()
            if active_for_email:
                raise ConflictError("this email already has an active self-service key")
            settings = connection.execute(
                """SELECT auto_issue_enabled, auto_issue_quota
                   FROM onboarding_settings WHERE settings_id = 1"""
            ).fetchone()
            device_already_claimed = bool(
                claim_device_hash
                and connection.execute(
                    """SELECT 1 FROM key_requests
                       WHERE claim_device_hash = ? AND status = 'auto_issued' LIMIT 1""",
                    (claim_device_hash,),
                ).fetchone()
            )
            auto_issue = bool(
                settings and settings["auto_issue_enabled"] == 1 and settings["auto_issue_quota"] > 0
                and claim_device_hash and not device_already_claimed
            )
            if device_already_claimed:
                review_reason = "device_limit"
            elif not claim_device_hash:
                review_reason = "missing_device_id"
            elif not settings or settings["auto_issue_enabled"] != 1 or settings["auto_issue_quota"] <= 0:
                review_reason = "quota_unavailable"
            else:
                review_reason = ""
            key_id = self._new_key_id() if auto_issue else ""
            token = self._new_user_token() if auto_issue else ""
            status = "auto_issued" if auto_issue else "pending"
            connection.execute(
                """INSERT INTO key_requests (
                    request_id, email, phone_number, contact, use_case, device_count, status,
                    activation_id, key_id, attribution_source, attribution_campaign,
                    attribution_landing, claim_device_hash, review_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request_id,
                    email,
                    phone_number,
                    contact,
                    use_case,
                    device_count,
                    status,
                    key_id,
                    attribution_source,
                    attribution_campaign,
                    attribution_landing,
                    claim_device_hash,
                    review_reason,
                    now,
                    now,
                ),
            )
            if auto_issue:
                try:
                    connection.execute(
                        """INSERT INTO user_keys (
                            key_id, label, phone_number, owner_ref, device_id, sim_slot,
                            token_hash, enabled, created_at, updated_at
                        ) VALUES (?, 'Self-service test', ?, ?, '', NULL, ?, 1, ?, ?)""",
                        (
                            key_id,
                            phone_number,
                            "request:" + request_id,
                            token_digest(token),
                            now,
                            now,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ConflictError("phone number already has an active key") from exc
                connection.execute(
                    """UPDATE onboarding_settings
                       SET auto_issue_quota = auto_issue_quota - 1, updated_at = ?
                       WHERE settings_id = 1 AND auto_issue_quota > 0""",
                    (now,),
                )
        return {
            "request_id": request_id,
            "status": status,
            "key_id": key_id,
            "key": token,
            "key_shown_once": bool(token),
            "auto_issue_blocked_reason": review_reason,
        }

    def get_onboarding_settings(
        self, public: bool = False, claim_device_id: Any = ""
    ) -> Dict[str, Any]:
        claim_device_hash = claim_device_digest(claim_device_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT auto_issue_enabled, auto_issue_quota, updated_at
                   FROM onboarding_settings WHERE settings_id = 1"""
            ).fetchone()
            device_already_claimed = bool(
                claim_device_hash
                and connection.execute(
                    """SELECT 1 FROM key_requests
                       WHERE claim_device_hash = ? AND status = 'auto_issued' LIMIT 1""",
                    (claim_device_hash,),
                ).fetchone()
            )
        settings = dict(row) if row else {"auto_issue_enabled": 0, "auto_issue_quota": 0, "updated_at": ""}
        available = bool(settings["auto_issue_enabled"] and settings["auto_issue_quota"] > 0)
        if public:
            return {
                "auto_issue_available": available,
                "auto_issue_remaining": int(settings["auto_issue_quota"]) if available else 0,
                "device_auto_issue_eligible": bool(claim_device_hash and not device_already_claimed),
                "device_already_claimed": device_already_claimed,
            }
        return {
            "auto_issue_enabled": bool(settings["auto_issue_enabled"]),
            "auto_issue_quota": int(settings["auto_issue_quota"]),
            "auto_issue_available": available,
            "updated_at": settings["updated_at"],
        }

    def update_onboarding_settings(self, enabled: Any, quota: Any) -> Dict[str, Any]:
        if not isinstance(enabled, bool):
            raise ValueError("auto_issue_enabled must be true or false")
        try:
            quota = int(quota)
        except (TypeError, ValueError) as exc:
            raise ValueError("auto_issue_quota must be a non-negative integer") from exc
        if quota < 0 or quota > 10000:
            raise ValueError("auto_issue_quota must be between 0 and 10000")
        with self._lock, self._connect() as connection:
            connection.execute(
                """UPDATE onboarding_settings
                   SET auto_issue_enabled = ?, auto_issue_quota = ?, updated_at = ?
                   WHERE settings_id = 1""",
                (1 if enabled else 0, quota, utc_now()),
            )
        return self.get_onboarding_settings()

    def list_key_requests(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT request_id, email, phone_number, contact, use_case, device_count, status,
                          activation_id, key_id, attribution_source, attribution_campaign,
                          attribution_landing, review_reason, created_at, updated_at
                   FROM key_requests ORDER BY created_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def create_activation_code(
        self, label: str = "", request_id: str = "", expires_in_days: int = 14
    ) -> Tuple[str, str, str]:
        request_id = clean_text(request_id, 64)
        label = clean_text(label, 128)
        if expires_in_days < 1 or expires_in_days > 365:
            raise ValueError("expires_in_days must be between 1 and 365")
        activation_id = self._new_activation_id()
        code = self._new_activation_code()
        now = utc_now()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat(
            timespec="seconds"
        )
        with self._lock, self._connect() as connection:
            if request_id:
                request = connection.execute(
                    "SELECT request_id, status FROM key_requests WHERE request_id = ?", (request_id,)
                ).fetchone()
                if not request:
                    raise ValueError("key request not found")
                if request["status"] != "pending":
                    raise ConflictError("key request has already been handled")
            connection.execute(
                """INSERT INTO activation_codes (
                    activation_id, request_id, label, code_hash, status, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'available', ?, ?, ?)""",
                (activation_id, request_id, label, token_digest(code), expires_at, now, now),
            )
            if request_id:
                connection.execute(
                    """UPDATE key_requests
                       SET status = 'approved', activation_id = ?, updated_at = ?
                       WHERE request_id = ?""",
                    (activation_id, now, request_id),
                )
        return activation_id, code, expires_at

    def list_activation_codes(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT activation_id, request_id, label, status, expires_at, redeemed_at,
                          redeemed_phone, key_id, created_at, updated_at
                   FROM activation_codes ORDER BY created_at DESC"""
            ).fetchall()
        now = datetime.now(timezone.utc)
        activation_codes = []
        for row in rows:
            activation = dict(row)
            if activation["status"] == "available":
                try:
                    expires_at = datetime.fromisoformat(activation["expires_at"])
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if now >= expires_at:
                        activation["status"] = "expired"
                except (TypeError, ValueError):
                    activation["status"] = "expired"
            activation_codes.append(activation)
        return activation_codes

    def disable_activation_code(self, activation_id: str) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE activation_codes SET status = 'disabled', updated_at = ?
                   WHERE activation_id = ? AND status = 'available'""",
                (utc_now(), clean_text(activation_id, 64)),
            )
            if cursor.rowcount != 1:
                raise ValueError("activation code is unavailable or missing")

    def redeem_activation_code(self, code: str, phone_number: str) -> Tuple[str, str, str]:
        code = clean_text(code, 128)
        if not code.startswith(ACTIVATION_CODE_PREFIX):
            raise ActivationError("activation code is invalid")
        phone_number = normalize_phone_number(phone_number)
        now = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT activation_id, request_id, label, status, expires_at
                   FROM activation_codes WHERE code_hash = ?""",
                (token_digest(code),),
            ).fetchone()
            if not row:
                raise ActivationError("activation code is invalid")
            if row["status"] != "available":
                raise ActivationError("activation code has already been used or disabled")
            try:
                expires_at = datetime.fromisoformat(row["expires_at"])
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError) as exc:
                raise ActivationError("activation code is invalid") from exc
            if datetime.now(timezone.utc) >= expires_at:
                raise ActivationError("activation code has expired")
            key_id = self._new_key_id()
            token = self._new_user_token()
            owner_ref = "request:" + row["request_id"] if row["request_id"] else "activation"
            try:
                connection.execute(
                    """INSERT INTO user_keys (
                        key_id, label, phone_number, owner_ref, device_id, sim_slot,
                        token_hash, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, '', NULL, ?, 1, ?, ?)""",
                    (key_id, row["label"], phone_number, owner_ref, token_digest(token), now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError("phone number already has an active key") from exc
            connection.execute(
                """UPDATE activation_codes
                   SET status = 'redeemed', redeemed_at = ?, redeemed_phone = ?, key_id = ?, updated_at = ?
                   WHERE activation_id = ?""",
                (now, phone_number, key_id, now, row["activation_id"]),
            )
            if row["request_id"]:
                connection.execute(
                    """UPDATE key_requests
                       SET status = 'redeemed', key_id = ?, updated_at = ?
                       WHERE request_id = ?""",
                    (key_id, now, row["request_id"]),
                )
        return key_id, token, row["label"]

    def issue_user_key(
        self,
        phone_number: str,
        label: str = "",
        owner_ref: str = "",
        device_id: str = "",
        sim_slot: Optional[int] = None,
    ) -> Tuple[str, str]:
        phone_number = normalize_phone_number(phone_number)
        device_id = clean_text(device_id, 128)
        if device_id and sim_slot not in (1, 2):
            raise ValueError("sim_slot must be 1 or 2 when device_id is provided")
        if not device_id:
            sim_slot = None
        key_id = self._new_key_id()
        token = self._new_user_token()
        now = utc_now()
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """INSERT INTO user_keys (
                        key_id, label, phone_number, owner_ref, device_id, sim_slot,
                        token_hash, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                    (
                        key_id,
                        clean_text(label, 128),
                        phone_number,
                        clean_text(owner_ref, 256),
                        device_id,
                        sim_slot,
                        token_digest(token),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictError("phone number or device SIM already has an active key") from exc
        return key_id, token

    def list_user_keys(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT key_id, label, phone_number, owner_ref, device_id, sim_slot,
                          enabled, created_at, updated_at, last_accessed
                   FROM user_keys ORDER BY created_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def authenticate_user_key(self, token: str) -> Optional[Dict[str, Any]]:
        if not token or not token.startswith(USER_KEY_PREFIX):
            return None
        digest = token_digest(token)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT key_id, label, phone_number, owner_ref, device_id, sim_slot,
                          enabled, created_at, updated_at
                   FROM user_keys WHERE token_hash = ? AND enabled = 1""",
                (digest,),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                "UPDATE user_keys SET last_accessed = ? WHERE key_id = ?",
                (utc_now(), row["key_id"]),
            )
        return dict(row)

    def rotate_user_key(self, key_id: str) -> str:
        token = self._new_user_token()
        now = utc_now()
        try:
            with self._lock, self._connect() as connection:
                cursor = connection.execute(
                    """UPDATE user_keys
                       SET token_hash = ?, enabled = 1, updated_at = ?
                       WHERE key_id = ?""",
                    (token_digest(token), now, clean_text(key_id, 64)),
                )
                if cursor.rowcount != 1:
                    raise ValueError("key not found")
        except sqlite3.IntegrityError as exc:
            raise ConflictError("phone number or device SIM already has an active key") from exc
        return token

    def disable_user_key(self, key_id: str) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE user_keys SET enabled = 0, updated_at = ? WHERE key_id = ?",
                (utc_now(), clean_text(key_id, 64)),
            )
            if cursor.rowcount != 1:
                raise ValueError("key not found")

    def unbind_user_key(self, key_id: str) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE user_keys
                   SET device_id = '', sim_slot = NULL, updated_at = ?
                   WHERE key_id = ?""",
                (utc_now(), clean_text(key_id, 64)),
            )
            if cursor.rowcount != 1:
                raise ValueError("key not found")

    def bind_user_key(
        self, key_id: str, device_id: str, sim_slot: Optional[int]
    ) -> Dict[str, Any]:
        device_id = clean_text(device_id, 128)
        if not device_id:
            raise ValueError("device_id is required")
        if sim_slot not in (1, 2):
            raise ValueError("sim_slot must be 1 or 2")
        now = utc_now()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT key_id, phone_number, device_id, sim_slot, enabled
                   FROM user_keys WHERE key_id = ?""",
                (clean_text(key_id, 64),),
            ).fetchone()
            if not row or row["enabled"] != 1:
                raise ValueError("key is disabled or missing")
            already_bound = bool(row["device_id"])
            if row["device_id"]:
                if row["device_id"] != device_id or row["sim_slot"] != sim_slot:
                    raise ConflictError("key is already bound to another device or SIM")
            else:
                collision = connection.execute(
                    """SELECT 1 FROM user_keys
                       WHERE enabled = 1 AND device_id = ? AND sim_slot = ?""",
                    (device_id, sim_slot),
                ).fetchone()
                if collision:
                    raise ConflictError("device SIM already has an active key")
                connection.execute(
                    """UPDATE user_keys
                       SET device_id = ?, sim_slot = ?, updated_at = ?
                       WHERE key_id = ?""",
                    (device_id, sim_slot, now, row["key_id"]),
                )
                connection.execute(
                    """INSERT INTO key_milestones (key_id, bound_at)
                       VALUES (?, ?)
                       ON CONFLICT(key_id) DO UPDATE SET
                         bound_at = CASE WHEN key_milestones.bound_at = ''
                                         THEN excluded.bound_at ELSE key_milestones.bound_at END""",
                    (row["key_id"], now),
                )
            device_token = secrets.token_urlsafe(32)
            connection.execute(
                """INSERT INTO device_credentials (
                    device_id, label, token_hash, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    label = excluded.label,
                    token_hash = excluded.token_hash,
                    enabled = 1,
                    updated_at = excluded.updated_at""",
                (
                    device_id,
                    "VibeSMS " + row["phone_number"],
                    token_digest(device_token),
                    now,
                    now,
                ),
            )
        return {
            "key_id": row["key_id"],
            "phone_number": row["phone_number"],
            "device_id": device_id,
            "sim_slot": sim_slot,
            "device_token": device_token,
            "already_bound": already_bound,
        }

    @staticmethod
    def _webhook_hint(webhook_url: str) -> str:
        token = urlparse(webhook_url).path.rsplit("/", 1)[-1]
        return "••••" + token[-6:] if token else "configured"

    def get_feishu_webhook(self, key_id: str) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT webhook_id, webhook_url, keywords_json, enabled, created_at,
                          updated_at, last_tested_at
                   FROM webhook_configs WHERE key_id = ? AND provider = 'feishu'""",
                (clean_text(key_id, 64),),
            ).fetchone()
            deliveries = connection.execute(
                """SELECT d.delivery_id, d.status, d.attempts, d.response_code,
                          d.last_error, d.created_at, d.updated_at, d.sent_at,
                          e.sender, e.received_at
                   FROM webhook_deliveries d
                   JOIN webhook_configs w ON w.webhook_id = d.webhook_id
                   JOIN events e ON e.event_id = d.event_id
                   WHERE w.key_id = ? AND w.provider = 'feishu'
                   ORDER BY d.delivery_id DESC LIMIT 20""",
                (clean_text(key_id, 64),),
            ).fetchall()
        if not row:
            return {"configured": False, "deliveries": []}
        return {
            "configured": True,
            "webhook_id": row["webhook_id"],
            "webhook_hint": self._webhook_hint(row["webhook_url"]),
            "keywords": json.loads(row["keywords_json"]),
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_tested_at": row["last_tested_at"],
            "deliveries": [dict(delivery) for delivery in deliveries],
        }

    def upsert_feishu_webhook(
        self, key_id: str, webhook_url: Any, keywords: Any, enabled: Any
    ) -> Dict[str, Any]:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be true or false")
        normalized_keywords = normalize_webhook_keywords(keywords)
        key_id = clean_text(key_id, 64)
        now = utc_now()
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT webhook_id, webhook_url FROM webhook_configs WHERE key_id = ?",
                (key_id,),
            ).fetchone()
            normalized_url = validate_feishu_webhook_url(webhook_url) if clean_text(webhook_url) else ""
            if not normalized_url:
                if not existing:
                    raise ValueError("webhook_url is required for the first configuration")
                normalized_url = existing["webhook_url"]
            webhook_id = existing["webhook_id"] if existing else "wh_" + secrets.token_hex(8)
            connection.execute(
                """INSERT INTO webhook_configs (
                       webhook_id, key_id, provider, webhook_url, keywords_json,
                       enabled, created_at, updated_at
                   ) VALUES (?, ?, 'feishu', ?, ?, ?, ?, ?)
                   ON CONFLICT(key_id) DO UPDATE SET
                       webhook_url = excluded.webhook_url,
                       keywords_json = excluded.keywords_json,
                       enabled = excluded.enabled,
                       updated_at = excluded.updated_at""",
                (
                    webhook_id,
                    key_id,
                    normalized_url,
                    json.dumps(normalized_keywords, ensure_ascii=False),
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
        return self.get_feishu_webhook(key_id)

    def delete_feishu_webhook(self, key_id: str) -> None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT webhook_id FROM webhook_configs WHERE key_id = ? AND provider = 'feishu'",
                (clean_text(key_id, 64),),
            ).fetchone()
            if not row:
                raise ValueError("Feishu webhook is not configured")
            connection.execute(
                "DELETE FROM webhook_deliveries WHERE webhook_id = ?", (row["webhook_id"],)
            )
            connection.execute(
                "DELETE FROM webhook_configs WHERE webhook_id = ?", (row["webhook_id"],)
            )

    @staticmethod
    def _send_feishu_payload(webhook_url: str, text: str, timeout: float = 5.0) -> int:
        payload = json.dumps(
            {"msg_type": "text", "content": {"text": text}}, ensure_ascii=False
        ).encode("utf-8")
        request = Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            response_code = int(response.status)
            response_body = response.read(4096).decode("utf-8", errors="replace")
        if response_code < 200 or response_code >= 300:
            raise WebhookDeliveryError("Feishu returned HTTP %d" % response_code)
        try:
            result = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError as exc:
            raise WebhookDeliveryError("Feishu returned invalid JSON") from exc
        business_code = result.get("code", result.get("StatusCode", 0))
        if business_code not in (0, "0", None):
            message = clean_text(result.get("msg", result.get("StatusMessage", "delivery rejected")), 200)
            raise WebhookDeliveryError("Feishu rejected the message: " + message)
        return response_code

    def test_feishu_webhook(self, key_id: str) -> Dict[str, Any]:
        key_id = clean_text(key_id, 64)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT webhook_id, webhook_url FROM webhook_configs
                   WHERE key_id = ? AND provider = 'feishu'""",
                (key_id,),
            ).fetchone()
        if not row:
            raise ValueError("Feishu webhook is not configured")
        response_code = self._send_feishu_payload(
            row["webhook_url"],
            "VibeSMS 飞书转发测试成功。\n这是一条配置验证消息，不包含真实短信内容。",
        )
        now = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE webhook_configs SET last_tested_at = ?, updated_at = ? WHERE webhook_id = ?",
                (now, now, row["webhook_id"]),
            )
        return {"delivered": True, "response_code": response_code, "tested_at": now}

    def _queue_feishu_delivery(
        self, connection: sqlite3.Connection, event: Dict[str, Any], key_id: str, now: str
    ) -> None:
        if event["event_type"] != "sms":
            return
        config = connection.execute(
            """SELECT webhook_id, keywords_json FROM webhook_configs
               WHERE key_id = ? AND provider = 'feishu' AND enabled = 1""",
            (key_id,),
        ).fetchone()
        if not config:
            return
        keywords = json.loads(config["keywords_json"])
        content = event["content"].casefold()
        if not any(str(keyword).casefold() in content for keyword in keywords):
            return
        connection.execute(
            """INSERT OR IGNORE INTO webhook_deliveries (
                   webhook_id, event_id, status, attempts, next_attempt_at,
                   created_at, updated_at
               ) VALUES (?, ?, 'pending', 0, ?, ?, ?)""",
            (config["webhook_id"], event["event_id"], now, now, now),
        )

    def deliver_due_webhooks(self, limit: int = 20) -> Dict[str, int]:
        sent = 0
        failed = 0
        now = utc_now()
        with self._lock, self._connect() as connection:
            due = connection.execute(
                """SELECT d.delivery_id, d.attempts, w.webhook_url,
                          e.sender, e.content, e.received_at, e.sim_slot,
                          k.phone_number
                   FROM webhook_deliveries d
                   JOIN webhook_configs w ON w.webhook_id = d.webhook_id
                   JOIN events e ON e.event_id = d.event_id
                   JOIN user_keys k ON k.key_id = w.key_id
                   WHERE w.enabled = 1
                     AND k.enabled = 1
                     AND d.status IN ('pending', 'failed')
                     AND d.attempts < 5
                     AND d.next_attempt_at <= ?
                   ORDER BY d.delivery_id ASC LIMIT ?""",
                (now, max(1, min(int(limit), 100))),
            ).fetchall()
        for delivery in due:
            attempt = int(delivery["attempts"]) + 1
            with self._lock, self._connect() as connection:
                claimed = connection.execute(
                    """UPDATE webhook_deliveries
                       SET status = 'sending', attempts = ?, updated_at = ?
                       WHERE delivery_id = ? AND status IN ('pending', 'failed')""",
                    (attempt, utc_now(), delivery["delivery_id"]),
                )
                if claimed.rowcount != 1:
                    continue
            message = (
                "【VibeSMS 短信】\n"
                f"号码：{delivery['phone_number']}\n"
                f"SIM：{delivery['sim_slot']}\n"
                f"发送方：{delivery['sender'] or '未知'}\n"
                f"时间：{delivery['received_at']}\n"
                f"内容：{delivery['content']}"
            )
            try:
                response_code = self._send_feishu_payload(delivery["webhook_url"], message)
            except (HTTPError, URLError, OSError, ValueError) as exc:
                failed += 1
                retry_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=min(300, 5 * (2 ** (attempt - 1))))
                ).isoformat(timespec="seconds")
                with self._lock, self._connect() as connection:
                    connection.execute(
                        """UPDATE webhook_deliveries
                           SET status = 'failed', response_code = ?, last_error = ?,
                               next_attempt_at = ?, updated_at = ?
                           WHERE delivery_id = ?""",
                        (
                            getattr(exc, "code", None),
                            clean_text(str(exc), 300),
                            retry_at,
                            utc_now(),
                            delivery["delivery_id"],
                        ),
                    )
                continue
            sent += 1
            delivered_at = utc_now()
            with self._lock, self._connect() as connection:
                connection.execute(
                    """UPDATE webhook_deliveries
                       SET status = 'sent', response_code = ?, last_error = '',
                           sent_at = ?, updated_at = ?
                       WHERE delivery_id = ?""",
                    (response_code, delivered_at, delivered_at, delivery["delivery_id"]),
                )
        return {"sent": sent, "failed": failed}

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
            if inserted and event["sim_slot"] in (1, 2):
                key_row = connection.execute(
                    """SELECT key_id FROM user_keys
                       WHERE enabled = 1 AND device_id = ? AND sim_slot = ?""",
                    (event["device_id"], event["sim_slot"]),
                ).fetchone()
                if key_row:
                    connection.execute(
                        """UPDATE key_milestones SET first_event_at = ?
                           WHERE key_id = ? AND bound_at != '' AND first_event_at = ''""",
                        (created_at, key_row["key_id"]),
                    )
                    self._queue_feishu_delivery(connection, event, key_row["key_id"], created_at)
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
            if sim_slot in (1, 2):
                key_row = connection.execute(
                    """SELECT key_id FROM user_keys
                       WHERE enabled = 1 AND device_id = ? AND sim_slot = ?""",
                    (device_id, sim_slot),
                ).fetchone()
                if key_row:
                    connection.execute(
                        """UPDATE key_milestones SET first_heartbeat_at = ?
                           WHERE key_id = ? AND bound_at != '' AND first_heartbeat_at = ''""",
                        (now, key_row["key_id"]),
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

    def list_key_events(
        self,
        key: Dict[str, Any],
        after_id: int = 0,
        limit: int = 100,
        event_type: str = "",
        newest_first: bool = False,
    ) -> List[Dict[str, Any]]:
        if not key.get("device_id") or key.get("sim_slot") not in (1, 2):
            return []
        clauses = ["device_id = ?", "sim_slot = ?", "id > ?"]
        params: List[Any] = [key["device_id"], key["sim_slot"], max(0, after_id)]
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        params.append(max(1, min(limit, 200)))
        fields = (
            "id, event_id, event_type, sender, content, received_at, sim_slot, "
            "sim_label, call_type, created_at"
        )
        order = "DESC" if newest_first else "ASC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT "
                + fields
                + " FROM events WHERE "
                + " AND ".join(clauses)
                + " ORDER BY id "
                + order
                + " LIMIT ?",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def key_status(self, key: Dict[str, Any], offline_seconds: int) -> Dict[str, Any]:
        device_id = clean_text(key.get("device_id"), 128)
        sim_slot = key.get("sim_slot")
        cursor = 0
        device: Optional[Dict[str, Any]] = None
        with self._lock, self._connect() as connection:
            if device_id and sim_slot in (1, 2):
                cursor = int(
                    connection.execute(
                        """SELECT COALESCE(MAX(id), 0) FROM events
                           WHERE device_id = ? AND sim_slot = ?""",
                        (device_id, sim_slot),
                    ).fetchone()[0]
                )
                row = connection.execute(
                    """SELECT device_id, last_seen, last_heartbeat, app_version,
                              battery, network_type
                       FROM devices WHERE device_id = ?""",
                    (device_id,),
                ).fetchone()
                if row:
                    device = dict(row)
        online = False
        seconds_since_seen: Optional[int] = None
        if device:
            try:
                last_seen = datetime.fromisoformat(device["last_seen"])
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                seconds_since_seen = max(
                    0, int((datetime.now(timezone.utc) - last_seen).total_seconds())
                )
                online = seconds_since_seen <= offline_seconds
            except (TypeError, ValueError):
                pass
        return {
            "key_id": key["key_id"],
            "phone_number": key["phone_number"],
            "bound": bool(device_id and sim_slot in (1, 2)),
            "device_id": device_id,
            "sim_slot": sim_slot,
            "online": online,
            "seconds_since_seen": seconds_since_seen,
            "cursor": cursor,
            "device": device,
        }

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

    def acquisition_funnel(self) -> Dict[str, Any]:
        """Return coarse, first-party acquisition milestones without event content or identifiers."""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT r.attribution_source AS source, r.attribution_campaign AS campaign,
                          COUNT(*) AS requested,
                          SUM(CASE WHEN r.key_id != '' THEN 1 ELSE 0 END) AS issued,
                          SUM(CASE WHEN m.bound_at != '' THEN 1 ELSE 0 END) AS bound,
                          SUM(CASE WHEN m.first_heartbeat_at != ''
                                   AND julianday(m.first_heartbeat_at) <= julianday(m.bound_at) + 1
                                   THEN 1 ELSE 0 END) AS heartbeat_24h,
                          SUM(CASE WHEN m.first_event_at != ''
                                   AND julianday(m.first_event_at) <= julianday(m.bound_at) + 1
                                   THEN 1 ELSE 0 END) AS first_event_24h
                   FROM key_requests r
                   LEFT JOIN key_milestones m ON m.key_id = r.key_id
                   GROUP BY r.attribution_source, r.attribution_campaign
                   ORDER BY requested DESC, source ASC, campaign ASC"""
            ).fetchall()
        channels = [
            {
                "source": row["source"], "campaign": row["campaign"],
                "requested": int(row["requested"] or 0), "issued": int(row["issued"] or 0),
                "bound": int(row["bound"] or 0), "heartbeat_24h": int(row["heartbeat_24h"] or 0),
                "first_event_24h": int(row["first_event_24h"] or 0),
            }
            for row in rows
        ]
        totals = {"requested": 0, "issued": 0, "bound": 0, "heartbeat_24h": 0, "first_event_24h": 0}
        for channel in channels:
            for key in totals:
                totals[key] += channel[key]
        return {"totals": totals, "channels": channels}


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
        if self.command != "HEAD":
            self.wfile.write(body)

    def _provided_token(self) -> str:
        provided = self.headers.get("X-Gateway-Token", "")
        if not provided:
            provided = self._bearer_token()
        return provided

    def _bearer_token(self) -> str:
        authorization = self.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return ""

    def _user_key_authorized(self) -> Optional[Dict[str, Any]]:
        return self.gateway_server.store.authenticate_user_key(self._bearer_token())

    def _user_key_unauthorized(self) -> None:
        body = json.dumps({"ok": False, "error": "valid VibeSMS key required"}).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Bearer realm="VibeSMS"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

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
        self.send_header("WWW-Authenticate", 'Basic realm="VibeSMS Admin", charset="UTF-8"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
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
        if path in {
            "/api/v1/webhooks/feishu",
            "/api/v1/webhooks/feishu/test",
            "/api/v1/webhooks/feishu/delete",
        }:
            key = self._user_key_authorized()
            if not key:
                self._user_key_unauthorized()
                return
            try:
                if path == "/api/v1/webhooks/feishu":
                    payload = self._read_json()
                    result = self.gateway_server.store.upsert_feishu_webhook(
                        key["key_id"],
                        payload.get("webhook_url"),
                        payload.get("keywords"),
                        payload.get("enabled"),
                    )
                    self._json(HTTPStatus.OK, {"ok": True, **result})
                    return
                if path == "/api/v1/webhooks/feishu/test":
                    result = self.gateway_server.store.test_feishu_webhook(key["key_id"])
                    self._json(HTTPStatus.OK, {"ok": True, **result})
                    return
                self.gateway_server.store.delete_feishu_webhook(key["key_id"])
                self._json(HTTPStatus.OK, {"ok": True, "deleted": True})
                return
            except (HTTPError, URLError, OSError, WebhookDeliveryError) as exc:
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": "Feishu delivery failed: " + clean_text(str(exc), 200)},
                )
                return
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return

        if path == "/api/v1/key-requests":
            try:
                payload = self._read_json()
                # A hidden honeypot keeps low-effort form spam out without profiling visitors.
                if clean_text(payload.get("website"), 256):
                    self._json(HTTPStatus.CREATED, {"ok": True, "request_id": "accepted"})
                    return
                result = self.gateway_server.store.submit_key_request(
                    payload.get("email"),
                    payload.get("use_case"),
                    payload.get("device_count"),
                    payload.get("contact"),
                    payload.get("phone_number"),
                    payload.get("attribution_campaign"),
                    payload.get("attribution_landing"),
                    payload.get("claim_device_id"),
                )
            except ConflictError as exc:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc)})
                return
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(HTTPStatus.CREATED, {"ok": True, **result})
            return

        if path == "/api/v1/activations/redeem":
            try:
                payload = self._read_json()
                key_id, token, label = self.gateway_server.store.redeem_activation_code(
                    payload.get("activation_code"), payload.get("phone_number")
                )
            except ConflictError as exc:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc)})
                return
            except ActivationError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(
                HTTPStatus.CREATED,
                {"ok": True, "key_id": key_id, "key": token, "label": label, "key_shown_once": True},
            )
            return

        if path == "/api/v1/bindings":
            key = self._user_key_authorized()
            if not key:
                self._user_key_unauthorized()
                return
            try:
                payload = self._read_json()
                result = self.gateway_server.store.bind_user_key(
                    key["key_id"],
                    clean_text(payload.get("device_id"), 128),
                    api_sim_slot(payload.get("sim_slot")),
                )
            except ConflictError as exc:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc)})
                return
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(
                HTTPStatus.OK if result["already_bound"] else HTTPStatus.CREATED,
                {"ok": True, **result, "device_token_shown_once": bool(result["device_token"])},
            )
            return

        key_match = re.fullmatch(
            r"/api/v1/admin/keys(?:/([^/]+)/(rotate|disable|unbind))?", path
        )
        if key_match:
            if not self._admin_authorized():
                self._admin_unauthorized()
                return
            try:
                payload = self._read_json()
                key_id, action = key_match.groups()
                if not action:
                    key_id, token = self.gateway_server.store.issue_user_key(
                        payload.get("phone_number"),
                        clean_text(payload.get("label"), 128),
                        clean_text(payload.get("owner_ref"), 256),
                        clean_text(payload.get("device_id"), 128),
                        api_sim_slot(payload.get("sim_slot")),
                    )
                    self._json(
                        HTTPStatus.CREATED,
                        {
                            "ok": True,
                            "key_id": key_id,
                            "key": token,
                            "key_shown_once": True,
                        },
                    )
                    return
                if action == "rotate":
                    token = self.gateway_server.store.rotate_user_key(key_id)
                    self._json(
                        HTTPStatus.OK,
                        {"ok": True, "key_id": key_id, "key": token, "key_shown_once": True},
                    )
                    return
                if action == "disable":
                    self.gateway_server.store.disable_user_key(key_id)
                else:
                    self.gateway_server.store.unbind_user_key(key_id)
            except ConflictError as exc:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc)})
                return
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(HTTPStatus.OK, {"ok": True, "key_id": key_id, "action": action})
            return

        activation_match = re.fullmatch(
            r"/api/v1/admin/activation-codes(?:/([^/]+)/disable)?", path
        )
        if activation_match:
            if not self._admin_authorized():
                self._admin_unauthorized()
                return
            try:
                payload = self._read_json()
                activation_id = activation_match.group(1)
                if activation_id:
                    self.gateway_server.store.disable_activation_code(activation_id)
                    self._json(
                        HTTPStatus.OK,
                        {"ok": True, "activation_id": activation_id, "action": "disable"},
                    )
                    return
                expires_in_days = int(payload.get("expires_in_days", 14))
                activation_id, code, expires_at = self.gateway_server.store.create_activation_code(
                    clean_text(payload.get("label"), 128),
                    clean_text(payload.get("request_id"), 64),
                    expires_in_days,
                )
            except ConflictError as exc:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc)})
                return
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "activation_id": activation_id,
                    "activation_code": code,
                    "expires_at": expires_at,
                    "activation_code_shown_once": True,
                },
            )
            return

        if path == "/api/v1/admin/onboarding-settings":
            if not self._admin_authorized():
                self._admin_unauthorized()
                return
            try:
                payload = self._read_json()
                settings = self.gateway_server.store.update_onboarding_settings(
                    payload.get("auto_issue_enabled"), payload.get("auto_issue_quota")
                )
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(HTTPStatus.OK, {"ok": True, **settings})
            return

        campaign_match = re.fullmatch(r"/api/v1/admin/campaigns(?:/([^/]+)/(enable|disable))?", path)
        if campaign_match:
            if not self._admin_authorized():
                self._admin_unauthorized()
                return
            try:
                payload = self._read_json()
                campaign_id, action = campaign_match.groups()
                if action:
                    self.gateway_server.store.set_campaign_enabled(campaign_id, action == "enable")
                    self._json(HTTPStatus.OK, {"ok": True, "campaign_id": campaign_id, "action": action})
                    return
                campaign = self.gateway_server.store.create_campaign(
                    payload.get("name"), payload.get("code"), payload.get("source"), payload.get("landing")
                )
            except ConflictError as exc:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc)})
                return
            except (ValueError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._json(HTTPStatus.CREATED, {"ok": True, "campaign": campaign})
            return

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
            if inserted:
                self.gateway_server.wake_webhook_worker()
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

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {"ok": True, "name": PRODUCT_NAME, "version": VERSION, **self.gateway_server.store.stats()},
            )
            return
        if path == "/api/v1/onboarding/status":
            claim_device_id = self.headers.get("X-VibeSMS-Claim-Device", "")
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self.gateway_server.store.get_onboarding_settings(
                        public=True, claim_device_id=claim_device_id
                    ),
                },
            )
            return

        if self._serve_static(path, public=True):
            return

        if path in {
            "/api/v1/status",
            "/api/v1/inbox",
            "/api/v1/otp/wait",
            "/api/v1/webhooks/feishu",
        }:
            key = self._user_key_authorized()
            if not key:
                self._user_key_unauthorized()
                return
            if path == "/api/v1/status":
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        **self.gateway_server.store.key_status(
                            key, self.gateway_server.offline_seconds
                        ),
                    },
                )
                return
            if path == "/api/v1/webhooks/feishu":
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, **self.gateway_server.store.get_feishu_webhook(key["key_id"])},
                )
                return
            try:
                after_id = max(0, int(query.get("after_id", ["0"])[0]))
                if path == "/api/v1/inbox":
                    limit = int(query.get("limit", ["100"])[0])
                    event_type = clean_text(query.get("type", [""])[0], 32).lower()
                    if event_type not in {"", "sms", "call", "test"}:
                        raise ValueError("type must be sms, call, test, or empty")
                    order = clean_text(query.get("order", ["asc"])[0], 8).lower()
                    if order not in {"asc", "desc"}:
                        raise ValueError("order must be asc or desc")
                    events = self.gateway_server.store.list_key_events(
                        key,
                        after_id=after_id,
                        limit=limit,
                        event_type=event_type,
                        newest_first=order == "desc",
                    )
                    cursor = max((event["id"] for event in events), default=after_id)
                    self._json(
                        HTTPStatus.OK,
                        {"ok": True, "events": events, "cursor": cursor},
                    )
                    return
                timeout = max(0.0, min(float(query.get("timeout", ["30"])[0]), 60.0))
            except (TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return

            cursor = after_id
            deadline = time.monotonic() + timeout
            while True:
                events = self.gateway_server.store.list_key_events(
                    key, after_id=cursor, limit=100, event_type="sms"
                )
                for event in events:
                    cursor = event["id"]
                    code = extract_otp(event["content"])
                    if code:
                        self._json(
                            HTTPStatus.OK,
                            {
                                "ok": True,
                                "status": "received",
                                "code": code,
                                "cursor": cursor,
                                "event": event,
                            },
                        )
                        return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._json(
                        HTTPStatus.OK,
                        {"ok": True, "status": "timeout", "cursor": cursor},
                    )
                    return
                time.sleep(min(0.25, remaining))

        protected_path = (
            path in {"/api/v1/events", "/api/v1/devices"}
            or path.startswith("/api/v1/admin/")
            or path in {"/admin", "/admin/"}
            or path.startswith("/admin/")
        )
        if protected_path and not self._admin_authorized():
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
        if path == "/api/v1/admin/keys":
            self._json(
                HTTPStatus.OK,
                {"ok": True, "keys": self.gateway_server.store.list_user_keys()},
            )
            return
        if path == "/api/v1/admin/key-requests":
            self._json(
                HTTPStatus.OK,
                {"ok": True, "requests": self.gateway_server.store.list_key_requests()},
            )
            return
        if path == "/api/v1/admin/activation-codes":
            self._json(
                HTTPStatus.OK,
                {"ok": True, "activation_codes": self.gateway_server.store.list_activation_codes()},
            )
            return
        if path == "/api/v1/admin/onboarding-settings":
            self._json(
                HTTPStatus.OK,
                {"ok": True, **self.gateway_server.store.get_onboarding_settings()},
            )
            return
        if path == "/api/v1/admin/campaigns":
            self._json(
                HTTPStatus.OK,
                {"ok": True, "campaigns": self.gateway_server.store.list_campaigns()},
            )
            return
        if path == "/api/v1/admin/acquisition-funnel":
            self._json(
                HTTPStatus.OK,
                {"ok": True, **self.gateway_server.store.acquisition_funnel()},
            )
            return
        if self._serve_static(path, public=False):
            return
        self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def _serve_static(self, request_path: str, public: bool) -> bool:
        names = (
            {
                "/": ("site/index.html", "text/html; charset=utf-8"),
                "/site/app.js": ("site/app.js", "text/javascript; charset=utf-8"),
                "/site/i18n.js": ("site/i18n.js", "text/javascript; charset=utf-8"),
                "/site/styles.css": ("site/styles.css", "text/css; charset=utf-8"),
                "/site/og-vibesms.jpg": ("site/og-vibesms.jpg", "image/jpeg"),
                "/privacy": ("privacy/index.html", "text/html; charset=utf-8"),
                "/privacy/": ("privacy/index.html", "text/html; charset=utf-8"),
                "/inbox": ("inbox/index.html", "text/html; charset=utf-8"),
                "/inbox/": ("inbox/index.html", "text/html; charset=utf-8"),
                "/inbox/app.js": ("inbox/app.js", "text/javascript; charset=utf-8"),
                "/inbox/styles.css": ("inbox/styles.css", "text/css; charset=utf-8"),
                "/apply": ("apply/index.html", "text/html; charset=utf-8"),
                "/apply/": ("apply/index.html", "text/html; charset=utf-8"),
                "/apply/app.js": ("apply/app.js", "text/javascript; charset=utf-8"),
                "/apply/styles.css": ("apply/styles.css", "text/css; charset=utf-8"),
                "/activate": ("activate/index.html", "text/html; charset=utf-8"),
                "/activate/": ("activate/index.html", "text/html; charset=utf-8"),
                "/activate/app.js": ("activate/app.js", "text/javascript; charset=utf-8"),
            }
            if public
            else {
                "/admin": ("admin/index.html", "text/html; charset=utf-8"),
                "/admin/": ("admin/index.html", "text/html; charset=utf-8"),
                "/admin/app.js": ("admin/app.js", "text/javascript; charset=utf-8"),
                "/admin/styles.css": ("admin/styles.css", "text/css; charset=utf-8"),
            }
        )
        item = names.get(request_path)
        if not item:
            return False
        file_name, content_type = item
        body = (STATIC_DIR / file_name).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        return True


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
        webhook_worker_enabled: bool = True,
    ):
        super().__init__(address, GatewayRequestHandler)
        self.store = store
        self.legacy_gateway_token = gateway_token
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.offline_seconds = max(30, offline_seconds)
        self.heartbeat_seconds = max(60, heartbeat_seconds)
        self._webhook_stop = threading.Event()
        self._webhook_wakeup = threading.Event()
        self._webhook_thread: Optional[threading.Thread] = None
        if bootstrap_device_id and gateway_token:
            self.store.ensure_device_credential(bootstrap_device_id, gateway_token, bootstrap_device_id)
        if webhook_worker_enabled:
            self._webhook_thread = threading.Thread(
                target=self._webhook_loop, name="vibesms-webhook-worker", daemon=True
            )
            self._webhook_thread.start()

    def _webhook_loop(self) -> None:
        while not self._webhook_stop.is_set():
            try:
                self.store.deliver_due_webhooks()
            except Exception as exc:  # Keep delivery faults isolated from the API server.
                print("Webhook worker error: %s" % clean_text(str(exc), 300), flush=True)
            self._webhook_wakeup.wait(30)
            self._webhook_wakeup.clear()

    def wake_webhook_worker(self) -> None:
        if self._webhook_thread:
            self._webhook_wakeup.set()

    def server_close(self) -> None:
        self._webhook_stop.set()
        self._webhook_wakeup.set()
        if self._webhook_thread and self._webhook_thread.is_alive():
            self._webhook_thread.join(timeout=2)
        super().server_close()


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
    webhook_worker_enabled: bool = True,
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
        webhook_worker_enabled,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VibeSMS server")
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
        "%s %s listening on http://%s:%s (db=%s)"
        % (PRODUCT_NAME, VERSION, args.host, args.port, args.database),
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
