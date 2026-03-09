# Backtesting Environment Notes

- **Session:** Sprint 1.1
- **Date:** 2026-03-08
- **Objective:** Validate reproducible backtesting environment before strategy implementation.

## Required Packages

From `requirements.txt`:

- `pandas`
- `numpy`
- `vectorbt`
- `TA-Lib`
- `tabulate`

Existing project dependencies remain unchanged (`requests`, `python-dotenv`).

## Verification Script

Run:

`python scripts/verify_backtest_env.py`

The script verifies:

1. Imports for pandas/numpy/vectorbt.
2. TA-Lib availability and basic RSI execution.
3. A minimal vectorbt long-only smoke run with fees and initial capital.

## Verified Runtime Snapshot

- Python: `3.14.3` (VirtualEnvironment: `.venv`)
- pandas: `2.3.3`
- numpy: `2.4.2`
- vectorbt: `0.28.4`
- TA-Lib: `0.6.8`
- tabulate: `0.10.0`

Smoke test status: **PASS** (`scripts/verify_backtest_env.py`)

## TA-Lib Fallback Strategy

If TA-Lib import fails on host:

1. Keep Sprint 1.1 passing with `WARN` status for TA-Lib.
2. Continue implementation with pluggable indicator backend design.
3. Use TA-Lib where available; fall back to pandas/numpy implementations per-indicator in Sprint 3.

## Error Correction Rule

Do **not** proceed to engine/indicator implementation until the smoke test returns `PASS` for core stack (`pandas`, `numpy`, `vectorbt`, and smoke run).
