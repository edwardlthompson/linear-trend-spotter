#!/usr/bin/env bash
# License compliance for root Python dependencies (uv lockfile)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for f in LICENSE THIRD_PARTY_LICENSES.md pyproject.toml uv.lock; do
  if [ ! -f "$f" ]; then
    echo "MISSING: $f"
    exit 1
  fi
done

if ! command -v uv &>/dev/null; then
  echo "ERROR: uv not found"
  exit 1
fi

uv sync --locked --extra dev --quiet

if ! uv run pip-licenses --format=csv --with-urls >/tmp/lts-licenses.csv 2>/dev/null; then
  echo "ERROR: pip-licenses failed"
  exit 1
fi

copyleft="$(tail -n +2 /tmp/lts-licenses.csv | grep -iE 'GPL|AGPL|LGPL|SSPL' || true)"
if [ -n "$copyleft" ]; then
  echo "ERROR: Copyleft licenses detected (require HUMAN approval per THIRD_PARTY_LICENSES.md):"
  echo "$copyleft"
  exit 1
fi

echo "License compliance check passed (no GPL/AGPL/LGPL/SSPL)"
