#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/home/edwardlthompson/linear-trend-spotter"
PYTHON_BIN="python3"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/setup_pythonanywhere.log"

mkdir -p "$LOG_DIR"

exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting PythonAnywhere setup"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: Project directory not found: $PROJECT_DIR"
  echo "Clone repo first, then re-run this script."
  exit 1
fi

cd "$PROJECT_DIR"

echo "Using Python: $($PYTHON_BIN --version)"

# Core packaging tools
$PYTHON_BIN -m pip install --upgrade pip setuptools wheel

# Install project dependencies
$PYTHON_BIN -m pip install -r requirements.txt

# Verify imports that are critical for this project
$PYTHON_BIN - <<'PY'
import importlib
mods = [
    "requests",
    "dotenv",
    "pandas",
    "numpy",
    "vectorbt",
    "talib",
    "tabulate",
    "matplotlib",
]
failed = []
for m in mods:
    try:
        importlib.import_module(m)
        print(f"OK: {m}")
    except Exception as e:
        print(f"FAIL: {m} -> {e}")
        failed.append(m)

if failed:
    raise SystemExit(f"Dependency verification failed for: {', '.join(failed)}")

print("All dependency imports verified.")
PY

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Setup completed successfully"
echo "Log file: $LOG_FILE"
