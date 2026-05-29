#!/usr/bin/env bash
set -euo pipefail

export DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

echo "[start] DATA_DIR=$DATA_DIR PORT=${PORT:-8080} USE_POLLING=${USE_POLLING:-0}"
echo "[start] launching unified server (web + telegram)..."
exec python server.py
