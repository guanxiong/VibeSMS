#!/usr/bin/env python3
"""Minimal VibeSMS Agent API client with no third-party dependencies."""

import argparse
import json
import os
import sys
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://sms.shareapi.ai"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read a Key-scoped VibeSMS inbox")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="show binding, terminal state, and current cursor")

    inbox = subparsers.add_parser("inbox", help="read SMS or call events")
    inbox.add_argument("--after-id", type=int, default=0)
    inbox.add_argument("--type", choices=("sms", "call", "test"), default="")
    inbox.add_argument("--limit", type=int, default=100)

    wait = subparsers.add_parser("wait-otp", help="wait for a 4-8 digit verification code")
    wait.add_argument("--after-id", type=int, required=True)
    wait.add_argument("--timeout", type=float, default=30.0)
    return parser


def config() -> tuple[str, str]:
    key = os.environ.get("VIBESMS_KEY", "").strip()
    if not key:
        raise ValueError("VIBESMS_KEY is not configured")
    base_url = os.environ.get("VIBESMS_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlparse(base_url)
    if not parsed.hostname or parsed.scheme not in {"http", "https"}:
        raise ValueError("VIBESMS_BASE_URL must be an HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("VIBESMS_BASE_URL must not contain credentials")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("VIBESMS_BASE_URL must use HTTPS outside localhost")
    return base_url, key


def request_json(base_url: str, key: str, path: str, timeout: float) -> Dict[str, Any]:
    request = Request(
        base_url + path,
        headers={"Accept": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("VibeSMS Key is invalid, disabled, or rotated (HTTP 401)") from exc
        raise RuntimeError("VibeSMS API returned HTTP %d" % exc.code) from exc
    except URLError as exc:
        raise RuntimeError("VibeSMS API connection failed: %s" % exc.reason) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("VibeSMS API returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("VibeSMS API returned an invalid response")
    return payload


def main() -> int:
    args = build_parser().parse_args()
    try:
        base_url, key = config()
        if args.command == "status":
            path = "/api/v1/status"
            timeout = 10.0
        elif args.command == "inbox":
            query = urlencode(
                {
                    "after_id": max(0, args.after_id),
                    "type": args.type,
                    "limit": max(1, min(args.limit, 200)),
                }
            )
            path = "/api/v1/inbox?" + query
            timeout = 10.0
        else:
            wait_timeout = max(0.0, min(args.timeout, 60.0))
            query = urlencode({"after_id": max(0, args.after_id), "timeout": wait_timeout})
            path = "/api/v1/otp/wait?" + query
            timeout = wait_timeout + 10.0
        print(json.dumps(request_json(base_url, key, path, timeout), ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError) as exc:
        print("vibesms: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
