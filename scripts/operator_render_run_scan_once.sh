#!/usr/bin/env bash
# Run one scan immediately on Render (paste into the worker Shell; do not run locally).
# Render Dashboard → linear-trend-spotter-worker → Shell, then:
#
#   bash scripts/operator_render_run_scan_once.sh
#
# Or one line (same entrypoint as the worker loop):
#   cd /opt/render/project/src && python3 scheduler.py
#
set -euo pipefail
cd "${PROJECT_DIR:-/opt/render/project/src}"
exec python3 scheduler.py
