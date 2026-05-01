# Backtesting library surface (Milestone P1)

This folder is the **import-safe** quantitative layer for hourly/4h/daily backtests. Host apps (scanner, future web API) should depend only on the entry points below.

## Public entry points

| Symbol | Role |
|--------|------|
| `BacktestDataLoader` | `backtesting/data_loader.py` — loads 1h OHLCV (CoinGecko → Polygon → CoinMarketCap), resamples to `1h` / `4h` / `1d`, validates frames, uses `PriceCache`. |
| `LoadResult` | Dataclass returned by `BacktestDataLoader.load`. |
| `run_backtests_for_final_results` | `backtesting/runner.py` — orchestrates vectorbt runs for qualified coins. |
| `notification_rows_for_symbol` | `backtesting/report.py` — shapes strategy rows for Telegram text. |
| `BacktestDataLoader.validate_ohlcv_frame` | Static validation helper. |

## Import boundaries (P3)

CI runs `python scripts/check_backtesting_imports.py`, which AST-scans `backtesting/**/*.py` and fails on imports of `notifications`, `telegram_bot`, or top-level `main`.

## Settings coupling

Loaders read `config.settings.settings` today for API rate limits and keys. Milestone **P2** (constructor-injected config) is optional follow-up for a second host without the full scanner `config.json`.
