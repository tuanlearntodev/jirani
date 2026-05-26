#!/usr/bin/env sh
set -eu

mkdir -p /app/uploads/books /app/uploads/covers

exec "$@"
