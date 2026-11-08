#!/bin/sh
set -eu

# One worker owns the SQLite engine and embedded workers in this appliance design.
# Migrations are applied by application lifespan when AUTO_MIGRATE=true.
exec uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --workers 1 \
    --no-access-log \
    --no-proxy-headers \
    --timeout-graceful-shutdown 30
