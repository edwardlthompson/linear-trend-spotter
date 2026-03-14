# Codebase Trim Audit — 2026-03-13

## Scope

Repository-wide trim of unused code/files and workflow streamlining with no intentional behavior changes to scanner outputs.

## What was removed

### Dead runtime code

- `processors/gain_filter.py`
  - No imports/usages in runtime or operational scripts.
  - Previously only re-exported in `processors/__init__.py`.
- `api/kraken_ohlcv.py`
  - No imports/usages in runtime or operational scripts.
  - Previously only re-exported in `api/__init__.py`.

### Non-runtime archive/debug artifacts

- Entire `.archive/` snapshot set was removed.
  - Included obsolete migration/debug scripts, shell snippets, old spec/plan snapshots, and historical logs.
  - None are part of current runtime flow.

### Demo-only scripts removed

- `scripts/send_two_image_notification_sample.py`
- `scripts/send_cell_table_notification_sample.py`
- `scripts/benchmark_first_filter_4000.py`

These were not referenced by current runtime entrypoints/tasks/docs required for operations.

## Streamlining changes

### `main.py` exchange listing stage optimization

- Replaced per-coin/per-exchange `is_listed(...)` calls with batched `batch_check_listings(...)` lookups.
- Expected effect:
  - fewer SQLite round-trips
  - lower scan overhead at large symbol counts
  - no logic change in `listed_on` results

## Explicit deviation note

I intentionally deviated from previous logic in Step 4 of scanner processing by switching from repeated row-level listing checks to batched checks.

- Why: previous implementation was operationally correct but inefficient at scale.
- Safety: it uses existing database API (`batch_check_listings`) and preserves output semantics.

## Kept intentionally

Operational and validation scripts were retained because they are still part of documented workflows:

- `scripts/run_full_unbounded_cg_first.py`
- `scripts/run_controlled_backtest_baseline.py`
- `scripts/render_backtest_report.py`
- `scripts/verify_backtest_env.py`
- `scripts/verify_backtest_data.py`
- `scripts/verify_backtest_engine.py`
- `scripts/verify_optimizer_bounds.py`
- `scripts/verify_indicator_signals.py`
- `scripts/verify_telegram.py`

## Validation

- Pylance error check on updated modules: no errors.
- Symbol search confirms removed dead exports/modules are no longer referenced.
