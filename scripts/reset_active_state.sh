#!/usr/bin/env bash
set -Eeuo pipefail

DATA_DIR="${DATA_DIR:-/var/data}"
DB_PATH="$DATA_DIR/scanner.db"

if [ ! -f "$DB_PATH" ]; then
  echo "ERROR: scanner DB not found at $DB_PATH"
  exit 1
fi

python3 - <<'PY'
import os
import sqlite3
from pathlib import Path

path = Path(os.getenv('DATA_DIR', '/var/data')) / 'scanner.db'
conn = sqlite3.connect(path)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM active_coins")
before = cur.fetchone()[0]
cur.execute("DELETE FROM active_coins")
conn.commit()
cur.execute("SELECT COUNT(*) FROM active_coins")
after = cur.fetchone()[0]
conn.close()
print(f"Cleared active_coins: {before} -> {after} in {path}")
PY

rm -f "$DATA_DIR/backtest_checkpoint.json" "$DATA_DIR/backtest_results.json" "$DATA_DIR/backtest_telemetry.jsonl"
echo "Removed backtest checkpoint/results artifacts from $DATA_DIR"
