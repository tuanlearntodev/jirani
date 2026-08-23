#!/usr/bin/env sh
set -eu

mkdir -p /app/uploads/books /app/uploads/covers /app/uploads/audio /app/uploads/vids /app/data

uv run --no-sync alembic upgrade head

exec "$@"
