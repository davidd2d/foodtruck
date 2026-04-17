#!/bin/zsh
set -euo pipefail

ROOT_DIR="${FOODTRUCK_ROOT:-/Users/david/Documents/foodtruck}"
PYTHON_BIN="${FOODTRUCK_PYTHON:-$ROOT_DIR/venv/bin/python}"
RETENTION_DAYS="${FOODTRUCK_RETENTION_DAYS:-90}"
BATCH_SIZE="${FOODTRUCK_RETENTION_BATCH_SIZE:-500}"

cd "$ROOT_DIR"
exec "$PYTHON_BIN" manage.py anonymize_old_orders --days "$RETENTION_DAYS" --batch-size "$BATCH_SIZE"