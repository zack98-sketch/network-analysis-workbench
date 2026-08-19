#!/bin/bash
set -e

mkdir -p /app/data/uploads /app/data/exports /app/data/index

echo "[Entrypoint] Starting sec-workbench..."

exec "$@"
