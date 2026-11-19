#!/usr/bin/env bash
set -euo pipefail

BUCKET="${1:?usage: backup.sh <bucket>}"
DATABASE="${DB_PATH:-/var/lib/dockship/dockship.db}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

sqlite3 "$DATABASE" ".backup '$TMP'"
aws s3 cp "$TMP" "s3://$BUCKET/backups/$(date +%F).db"
