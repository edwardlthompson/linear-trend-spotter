#!/usr/bin/env bash
# Same checks as .github/workflows/ci.yml — used by Render native build for parity.
set -euxo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

uv sync --locked --extra dev
uv run ruff check .
uv run python scripts/check_exchange_print_ascii.py
uv run mypy config notifications --follow-imports=skip --ignore-missing-imports
uv run python scripts/check_backtesting_imports.py
uv run python scripts/verify_backtest_env.py
uv run python -m compileall -q .
uv run python -m pytest tests/ -q
