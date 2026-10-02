#!/bin/sh
# Saige API container entrypoint: apply migrations, then serve.
# Works on Docker Compose and on hosts that inject $PORT (Render, Railway, Fly).
set -e
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic -c services/api/alembic.ini upgrade head
fi
exec uvicorn saige_api.main:create_app --factory \
  --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --no-server-header
