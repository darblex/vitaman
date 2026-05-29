#!/usr/bin/env bash
set -euo pipefail

export DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

echo "[start] DATA_DIR=$DATA_DIR PORT=${PORT:-8080}"
echo "[start] launching web server..."
python server.py &
WEB_PID=$!

cleanup() {
  kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "[start] launching telegram bot..."
python bot_new.py
