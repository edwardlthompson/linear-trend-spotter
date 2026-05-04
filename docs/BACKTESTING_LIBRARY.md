# Backtesting library surface (Milestone P1)

This folder is the **import-safe** quantitative layer for hourly/4h/daily backtests. Host apps (scanner, future web API) should depend only on the entry points below.

## Public entry points

| Symbol | Role |
|--------|------|
| `BacktestDataLoader` | `backtesting/data_loader.py` — loads 1h OHLCV (CoinGecko → Polygon → CoinMarketCap), resamples to `1h` / `4h` / `1d`, validates frames, uses `PriceCache`. |
| `LoadResult` | Dataclass returned by `BacktestDataLoader.load`. |
| `run_backtests_for_final_results` | `backtesting/runner.py` — orchestrates vectorbt runs for qualified coins. |
| `notification_rows_for_symbol` | `backtesting/report.py` — shapes strategy rows for snapshot/export text. |
| `BacktestDataLoader.validate_ohlcv_frame` | Static validation helper. |
| `BacktestLoaderParams` | `backtesting/params.py` — frozen knobs for `BacktestDataLoader` (CG rate limit, CMC key string, L1 OHLCV min-bar gates). |
| `BacktestRunnerParams` | Same module — orchestration fields for `run_backtests_for_final_results` (includes nested `loader`). |
| `loader_params_from_settings` / `runner_params_from_settings` | Map the integrated worker’s `config.settings` when the host omits explicit params. |

## Import boundaries (P3)

CI runs `python scripts/check_backtesting_imports.py`, which AST-scans `backtesting/**/*.py` and fails on imports of `notifications` or top-level `main`.

## Settings coupling (P2)

- **`BacktestDataLoader(..., loader_params=…)`** — pass `BacktestLoaderParams` so a second host does not need the scanner `config.json`. If omitted, `loader_params_from_settings()` runs once inside `__init__` (imports `config.settings`).
- **`run_backtests_for_final_results(..., params=…)`** — pass `BacktestRunnerParams` (with its nested `loader`) for the same reason. If omitted, `runner_params_from_settings()` fills paths, workers, timeouts, and fee/capital from `config.settings`.
- Importing **`backtesting.params`** does **not** import `config.settings` until you call `loader_params_from_settings()` / `runner_params_from_settings()`. **`backtesting.data_loader`** pulls `pandas` and API clients on import, but still avoids `config.settings` until `BacktestDataLoader` is constructed without an explicit `loader_params`.
