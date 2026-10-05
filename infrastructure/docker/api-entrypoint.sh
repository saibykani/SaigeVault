#!/bin/sh
# Saige API container entrypoint. MongoDB indexes are created at startup.
# Works on Docker Compose and on hosts that inject $PORT (Render, Railway, Fly).
set -e
exec uvicorn saige_api.main:create_app --factory \
  --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --no-server-header
