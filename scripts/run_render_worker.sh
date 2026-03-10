#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/render/project/src}"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/.render-data}"
SCAN_INTERVAL_SECONDS="${SCAN_INTERVAL_SECONDS:-3600}"
LOG_DIR="$DATA_DIR/logs"
LOG_FILE="$LOG_DIR/render_worker.log"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Render worker started" | tee -a "$LOG_FILE"
echo "PROJECT_DIR=$PROJECT_DIR DATA_DIR=$DATA_DIR INTERVAL=${SCAN_INTERVAL_SECONDS}s" | tee -a "$LOG_FILE"

while true; do
  started="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "[$started] Starting scheduled scan" | tee -a "$LOG_FILE"

  if python3 scheduler.py >> "$LOG_FILE" 2>&1; then
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Scan finished successfully" | tee -a "$LOG_FILE"
  else
    exit_code=$?
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Scan failed (exit $exit_code)" | tee -a "$LOG_FILE"
  fi

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Sleeping ${SCAN_INTERVAL_SECONDS}s" | tee -a "$LOG_FILE"
  sleep "$SCAN_INTERVAL_SECONDS"
done
