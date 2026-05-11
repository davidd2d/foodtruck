#!/usr/bin/env bash
set -euo pipefail

# Usage in production (example - OpenAgenda):
#   OPENAGENDA_API_KEY="your_public_key" \
#   # optional: OPENAGENDA_AGENDA_UIDS="12345678,87654321" \
#   /opt/foodtruck/scripts/sync_events_cron.sh
#
# Usage with a custom JSON feed:
#   ANALYTICS_EVENTS_SOURCE_URL="https://example.com/events.json" \
#   /opt/foodtruck/scripts/sync_events_cron.sh
#
# If no env var is set, synthetic seed events are generated (development).

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"
PYTHON_BIN="$VENV_DIR/bin/python"
MANAGE_PY="$PROJECT_DIR/manage.py"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[sync_events] Python not found in venv: $PYTHON_BIN" >&2
  exit 1
fi

if [[ -n "${OPENAGENDA_API_KEY:-}" ]]; then
  MODE="openagenda"
  EXTRA_ARGS=()
elif [[ -n "${ANALYTICS_EVENTS_SOURCE_URL:-}" ]]; then
  MODE="fetch"
  EXTRA_ARGS=(--source-url "$ANALYTICS_EVENTS_SOURCE_URL")
else
  MODE="seed"
  EXTRA_ARGS=()
fi

echo "[sync_events] Starting in mode=$MODE"
"$PYTHON_BIN" "$MANAGE_PY" sync_events --mode "$MODE" "${EXTRA_ARGS[@]}"
echo "[sync_events] Completed"
