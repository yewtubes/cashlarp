#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
name="cashlarp-$(date -u +%Y%m%dT%H%M%SZ)-$$.sqlite3"
tmp="/tmp/$name"
trap 'docker compose exec -T cashlarp rm -f "$tmp" >/dev/null 2>&1 || true' EXIT
docker compose exec -T cashlarp python -c 'import sqlite3,sys; source=sqlite3.connect("file:/app/data/sandbox.sqlite3?mode=ro",uri=True); target=sqlite3.connect(sys.argv[1]); source.backup(target);target.close();source.close()' "$tmp"
docker compose cp "cashlarp:$tmp" "backups/$name"
printf 'Backup: backups/%s\n' "$name"
