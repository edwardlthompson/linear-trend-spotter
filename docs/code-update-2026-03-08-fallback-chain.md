# Code Update - 2026-03-08 - Fallback Chain Integration

## Session 1 - Production fallback integration

- Added `api/price_history_fallback.py` with reliability-first 30d daily fallback chain:
  1. Polygon aggregates (`X:{SYMBOL}USD`, 1-day candles)
  2. CoinMarketCap historical quotes
- Integrated fallback in `main.py` Step 7 (uniformity history fetch):
  - Primary remains CoinGecko market chart (`interval='daily'`)
  - Fallback path triggers when CoinGecko data is missing or incomplete
  - Scanner now only skips a coin after all providers fail or return insufficient points

## Session 2 - Reliability tuning and explicit deviation

- **Deviation from prior logic (intentional):** reduced CoinGecko ticker retry behavior in `api/coingecko.py`.
  - Previous behavior could wait through long retry/backoff loops on `/tickers` (non-critical to final trend selection).
  - New behavior is fail-fast for ticker fetches (`max_retries=1`) and conservative throughput cap (`12 calls/minute` upper bound).
- **Why this deviation was necessary:** long ticker backoff stalls delayed/blocked full scans without materially improving final candidate quality.

## Session 3 - Runtime validation

- Ran full scanner and captured output in `scanner_run_latest.log`.
- Completed end-to-end scan successfully:
  - `New entries: 0, Exits: 0`
  - `Saved 2 results`
  - `Scan complete`
- Telegram path was initialized, but no entry/exit notifications were emitted in this run because there were no state changes.
- Fallback client live check validated with configured keys (`BTC` returned 31 points from Polygon).
