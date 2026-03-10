#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/home/edwardlthompson/linear-trend-spotter"
LOG_DIR="$PROJECT_DIR/logs"
TIMESTAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
LOG_FILE="$LOG_DIR/manual_run_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: Project directory not found: $PROJECT_DIR"
  exit 1
fi

cd "$PROJECT_DIR"

if [ ! -f "scheduler.py" ]; then
  echo "ERROR: scheduler.py not found in $PROJECT_DIR"
  exit 1
fi

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting manual scanner run"
echo "Project: $PROJECT_DIR"
echo "Log: $LOG_FILE"

python3 scheduler.py 2>&1 | tee -a "$LOG_FILE"
run_status=${PIPESTATUS[0]}

if [ "$run_status" -ne 0 ]; then
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Manual scanner run failed (exit $run_status)"
  exit "$run_status"
fi

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Manual scanner run completed successfully"
