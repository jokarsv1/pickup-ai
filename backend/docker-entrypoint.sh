#!/bin/sh
# Starts as root only to give the app user its data folder (Fly volumes mount as root), then
# drops privileges, runs migrations and serves.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p /data/recordings /app/recordings 2>/dev/null || true
  chown -R pickup:pickup /data /app/recordings 2>/dev/null || true
  exec runuser -u pickup -- "$0" "$@"
fi
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
