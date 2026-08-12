#!/usr/bin/env python3
"""Install and provision a VibeSMS Android terminal through an authorized ADB device."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional
from urllib.request import urlopen

from vibesms import config, request_json


RELEASE_VERSION = "0.4.9"
RELEASE_BASE = "https://github.com/guanxiong/VibeSMS/releases/download/v" + RELEASE_VERSION
APK_NAME = "VibeSMS-%s.apk" % RELEASE_VERSION
PACKAGE = "ai.shareapi.vibesms"
PROVISION_COMPONENT = PACKAGE + "/.ProvisionReceiver"
PROVISION_ACTION = "ai.shareapi.vibesms.action.PROVISION"
REQUIRED_PERMISSIONS = (
    "android.permission.RECEIVE_SMS",
    "android.permission.READ_PHONE_STATE",
)
OPTIONAL_PERMISSIONS = (
    "android.permission.READ_CALL_LOG",
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Install and provision VibeSMS over ADB")
    value.add_argument("--sim-slot", type=int, choices=(1, 2), required=True)
    value.add_argument("--serial", help="ADB serial; required only when multiple devices are attached")
    value.add_argument("--apk", type=Path, help="use a local signed APK instead of GitHub Releases")
    value.add_argument("--timeout", type=float, default=45.0)
    return value


def run_adb(adb: str, serial: str, arguments: List[str], label: str) -> str:
    process = subprocess.run(
        [adb, "-s", serial, *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=90,
    )
    if process.returncode != 0:
        detail = process.stdout.strip().splitlines()
        suffix = ": " + detail[-1][:240] if detail else ""
        raise RuntimeError(label + " failed" + suffix)
    return process.stdout


def verify_provision_result(output: str) -> None:
    matches = re.findall(r"result=(-?\d+)(?:,\s*data=\"([^\"]*)\")?", output)
    if not matches:
        raise RuntimeError("terminal provisioning returned no receiver result")
    result, detail = matches[-1]
    if int(result) != 0:
        raise RuntimeError("terminal provisioning rejected the request: " + (detail or "result " + result))


def choose_device(adb: str, requested: Optional[str]) -> str:
    process = subprocess.run(
        [adb, "devices"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
    )
    if process.returncode != 0:
        raise RuntimeError("cannot list ADB devices")
    states = {}
    for line in process.stdout.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            states[parts[0]] = parts[1]
    if requested:
        state = states.get(requested)
        if state != "device":
            raise RuntimeError("requested ADB device is not authorized (state=%s)" % (state or "missing"))
        return requested
    authorized = [serial for serial, state in states.items() if state == "device"]
    unauthorized = [serial for serial, state in states.items() if state == "unauthorized"]
    if not authorized:
        if unauthorized:
            raise RuntimeError("unlock the phone and approve the USB debugging prompt")
        raise RuntimeError("no Android device is connected over ADB")
    if len(authorized) > 1:
        raise RuntimeError("multiple Android devices are connected; rerun with --serial")
    return authorized[0]


def download_verified_apk(directory: Path) -> Path:
    sums_url = RELEASE_BASE + "/SHA256SUMS"
    apk_url = RELEASE_BASE + "/" + APK_NAME
    with urlopen(sums_url, timeout=30) as response:
        sums = response.read().decode("utf-8")
    expected = ""
    for line in sums.splitlines():
        fields = line.strip().split()
        if len(fields) >= 2 and fields[-1].lstrip("*") == APK_NAME:
            expected = fields[0].lower()
            break
    if len(expected) != 64:
        raise RuntimeError("release checksum is missing or invalid")
    apk = directory / APK_NAME
    digest = hashlib.sha256()
    with urlopen(apk_url, timeout=60) as response, apk.open("wb") as output:
        while True:
            block = response.read(1024 * 128)
            if not block:
                break
            output.write(block)
            digest.update(block)
    if digest.hexdigest().lower() != expected:
        raise RuntimeError("downloaded APK checksum does not match SHA256SUMS")
    return apk


def wait_until_online(base_url: str, key: str, timeout: float) -> dict:
    deadline = time.monotonic() + max(5.0, min(timeout, 120.0))
    latest = {}
    while time.monotonic() < deadline:
        latest = request_json(base_url, key, "/api/v1/status", 10.0)
        if latest.get("bound") and latest.get("online"):
            return latest
        time.sleep(1.0)
    if latest.get("bound"):
        raise RuntimeError("terminal is bound but its heartbeat is not online yet")
    raise RuntimeError("terminal binding was not visible before the timeout")


def main() -> int:
    args = parser().parse_args()
    try:
        base_url, key = config()
        adb = shutil.which("adb")
        if not adb:
            raise RuntimeError("adb is not installed or is not on PATH")
        serial = choose_device(adb, args.serial)
        with tempfile.TemporaryDirectory(prefix="vibesms-android-") as temp:
            apk = args.apk.expanduser().resolve() if args.apk else download_verified_apk(Path(temp))
            if not apk.is_file():
                raise RuntimeError("signed APK does not exist: %s" % apk)
            run_adb(adb, serial, ["install", "-r", "-g", str(apk)], "APK installation")
            warnings = []
            for permission in REQUIRED_PERMISSIONS:
                run_adb(
                    adb,
                    serial,
                    ["shell", "pm", "grant", PACKAGE, permission],
                    "granting " + permission,
                )
            for permission in OPTIONAL_PERMISSIONS:
                try:
                    run_adb(
                        adb,
                        serial,
                        ["shell", "pm", "grant", PACKAGE, permission],
                        "granting " + permission,
                    )
                except RuntimeError:
                    warnings.append(permission + " was not granted; caller numbers may be unavailable")
            try:
                run_adb(
                    adb,
                    serial,
                    ["shell", "dumpsys", "deviceidle", "whitelist", "+" + PACKAGE],
                    "battery optimization exemption",
                )
            except RuntimeError:
                warnings.append(
                    "battery optimization exemption was not applied; enable lock-screen keepalive in the app"
                )
            # Avoid a host shell so the Key is not expanded, logged, or printed by shell tooling.
            provision_output = run_adb(
                adb,
                serial,
                [
                    "shell",
                    "am",
                    "broadcast",
                    "--receiver-foreground",
                    "-a",
                    PROVISION_ACTION,
                    "-n",
                    PROVISION_COMPONENT,
                    "--es",
                    "vibesms_key",
                    key,
                    "--ei",
                    "sim_slot",
                    str(args.sim_slot),
                ],
                "terminal provisioning",
            )
            verify_provision_result(provision_output)
            status = wait_until_online(base_url, key, args.timeout)
            run_adb(
                adb,
                serial,
                ["shell", "am", "start", "-n", PACKAGE + "/.MainActivity"],
                "opening VibeSMS",
            )
        print(
            json.dumps(
                {
                    "ok": True,
                    "serial": serial,
                    "sim_slot": args.sim_slot,
                    "bound": bool(status.get("bound")),
                    "online": bool(status.get("online")),
                    "device_id": status.get("device_id", ""),
                    "warnings": warnings,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print("vibesms-setup: %s" % error, file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
