#!/usr/bin/env bash
# Same checks as .github/workflows/ci.yml — used by Render native build for parity.
set -euxo pipefail
python -m pip install --upgrade pip wheel
python -m pip install -r requirements-ci.txt
python -m pip install "ruff>=0.8.0,<0.13"
python -m ruff check .
python scripts/check_exchange_print_ascii.py
python -m mypy config notifications --follow-imports=skip --ignore-missing-imports
python scripts/check_backtesting_imports.py
python scripts/verify_backtest_env.py
python -m compileall -q .
python -m pytest tests/ -q
