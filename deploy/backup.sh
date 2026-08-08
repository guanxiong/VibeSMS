#!/bin/sh
set -eu

container="${SMS_GATEWAY_CONTAINER:-sms-gateway}"
host_backup_dir="/opt/sms-gateway/data/backups"
timestamp="$(date -u '+%Y%m%dT%H%M%SZ')"
container_backup="/data/backups/gateway-${timestamp}.db"

install -d -m 700 "$host_backup_dir"

docker exec "$container" python -c '
import sqlite3
import sys

source = sqlite3.connect("/data/gateway.db")
target = sqlite3.connect(sys.argv[1])
with target:
    source.backup(target)
result = target.execute("PRAGMA integrity_check").fetchone()[0]
source.close()
target.close()
if result != "ok":
    raise SystemExit(f"backup integrity check failed: {result}")
' "$container_backup"

find "$host_backup_dir" -type f -name 'gateway-*.db' -mtime +30 -delete
printf 'created %s\n' "$host_backup_dir/gateway-${timestamp}.db"
