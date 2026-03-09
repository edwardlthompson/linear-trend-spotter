# Linear Trend Spotter

Automated full-exchange scanner focused on identifying sustained trend quality (not one-candle pumps), with integrated multi-strategy backtesting to validate and rank opportunities before alerting.

## Key Features

1. **Trend Identification (Primary):** Evaluates the full exchange universe and identifies sustained, high-quality trends through strict multi-stage qualification.
2. **Integrated Backtesting (High-Value Validation):** Runs multi-strategy, multi-timeframe backtests only after trend qualification and ranks opportunities for alerts.
3. **Actionable Telegram Alerts:** Sends enriched entry/exit notifications with charting and backtest context.
4. **Resilient Data/Fallback Pipeline:** Uses CoinGecko-first data sourcing with fallback paths for continuity.

[![Telegram Group](https://img.shields.io/badge/Telegram-Join%20Group-blue?logo=telegram)](https://t.me/+pmZewVhuEFJjYTIx)

---

## What It Does

Linear Trend Spotter scans all symbols listed across target exchanges (default: Coinbase, Kraken, MEXC), then applies a strict multi-step qualification pipeline:

1. CoinMarketCap snapshot pull (up to 2500 coins; controlled by `TOP_COINS_LIMIT`)
2. Exchange listing universe build (all symbols in `exchange_listings`)
3. Gain/volume filter
4. CoinGecko ID mapping
5. Exchange-volume enrichment (CoinGecko tickers)
6. 30-day uniformity scoring from market chart history
7. **Backtesting stage (featured):** optional multi-strategy, multi-timeframe backtests on final-stage qualified coins
8. Entry/exit detection vs active list
9. Telegram notifications (single combined image when chart available; fallback supported)
10. History persistence + metrics/log summary

---

## Current Qualification Rules

Qualification determines which coins enter the **backtesting stage** (when enabled) and therefore which backtest-ranked strategy outputs are included in alerts.

### Filter 1: Volume + gains

- 24h CMC volume must be `>= MIN_VOLUME_M` (default `1,000,000`)
- 7d gain must be `> 7%`
- 30d gain must be `> 30%`
- 30d gain must be strictly higher than 7d gain (`30d > 7d`)
- Stablecoins are excluded

### Filter 2: Uniformity

- Uses 30-day price history (CoinGecko market chart)
- Computes a uniformity score from 0–100
- Must pass `UNIFORMITY_MIN_SCORE` (default `55`)
- Must also have positive 30d return

---

## Notification Behavior

### Entry notifications

- Sent once when a coin newly enters qualified state
- Includes:
  - Coin name/symbol with CMC link
  - 7d and 30d gains
  - Uniformity score
  - **Total 24h volume (CMC)**
  - Exchange-level volumes (Coinbase/Kraken/MEXC)
- Sends a **single combined image** (one ping) containing:
  - Price chart (top)
  - Ranked backtest strategy table with bordered cells (bottom)
- Strategy table columns:
  - `Indicator | TF | Key Settings | Stop Loss % | Final $ | Net % | Trades | Win %`
- Cell text wraps automatically when long values overflow
- If Chart-IMG fails, chart generation falls back to cached `ohlcv_cache` 1h data
- If no chart can be built, message gracefully degrades to text-only

### Exit notifications

- Sent once when a previously active coin leaves qualification
- Includes **precise exit reason** (first failed stage), for example:
  - 24h volume below threshold
  - 7d/30d threshold violation
  - `30d <= 7d`
  - Missing CMC/CoinGecko data
  - Uniformity score below threshold

---

## Caching + Rate Limit Strategy

- CoinGecko ticker requests use adaptive retry/backoff + jitter and `Retry-After` handling
- Non-critical ticker fetches fail fast after capped retries to prevent full-run stalls
- Exchange-volume cache TTL: 24h (`exchange_volume_cache`)
- Price/uniformity cache TTL: 6h (`price_cache`)

---

## Configuration

### 1) Environment variables (`.env`)

```env
CMC_API_KEY=your_cmc_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
CHART_IMG_API_KEY=your_chart_img_api_key_optional
```

### 2) App config (`config.json`)

Start from `config.json.example`:

```powershell
Copy-Item config.json.example config.json
```

Available parameters (defaults from `config/settings.py`):

| Key | Default | Purpose |
| --- | ---: | --- |
| `MIN_VOLUME_M` | `1000000` | Minimum 24h CMC volume gate |
| `TARGET_EXCHANGES` | `['coinbase','kraken','mexc']` | Exchanges scanned/listed |
| `UNIFORMITY_MIN_SCORE` | `55` | Uniformity filter cutoff |
| `UNIFORMITY_PERIOD` | `30` | Days used for score window |
| `TOP_COINS_LIMIT` | `2500` | General list limit control |
| `ENTRY_NOTIFICATIONS` | `true` | Enable entry alerts |
| `EXIT_NOTIFICATIONS` | `true` | Enable exit alerts |
| `RETRY_MAX_ATTEMPTS` | `3` | Generic retry attempts |
| `RETRY_DELAY` | `2` | Base retry delay |
| `RETRY_BACKOFF` | `2` | Retry backoff factor |
| `COINGECKO_CALLS_PER_MINUTE` | `30` | CoinGecko pacing target |
| `CMC_CALLS_PER_MINUTE` | `333` | CMC pacing target |
| `CACHE_GECKO_ID_DAYS` | `30` | Mapping cache TTL |
| `CACHE_EXCHANGE_HOURS` | `24` | Exchange-volume cache TTL |
| `CACHE_PRICE_HOURS` | `6` | Price/uniformity cache TTL |
| `CIRCUIT_FAILURE_THRESHOLD` | `5` | Circuit breaker fail threshold |
| `CIRCUIT_RECOVERY_TIMEOUT` | `60` | Circuit recovery timeout (sec) |
| `BACKTEST_ENABLED` | `false` | Enable integrated post-filter backtesting |
| `BACKTEST_REQUIRE_TARGET_EXCHANGE` | `false` | When `true`, gate backtests by `BACKTEST_EXCHANGES` |
| `BACKTEST_EXCHANGES` | `['kraken']` | Exchange allowlist used only when exchange gating is enabled |
| `BACKTEST_STARTING_CAPITAL` | `1000` | Starting capital per simulated strategy run |
| `BACKTEST_FEE_BPS_ROUND_TRIP` | `52` | Round-trip taker fee in bps |
| `BACKTEST_MAX_PARAM_COMBOS` | `100` | Max param combos per indicator/timeframe |
| `BACKTEST_PARALLEL_WORKERS` | `4` | Process workers for per-coin backtesting |
| `BACKTEST_MAX_COINS_PER_RUN` | `0` | Safety cap for eligible coins per scanner run (`0` = unlimited) |
| `BACKTEST_TIMEFRAMES` | `['1h','4h','1d']` | Timeframes to evaluate for each coin |
| `USE_14D_FILTER` | `false` | Reserved feature flag |

---

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Initialize/refresh support data:

```powershell
python update_mappings.py
python update_exchanges.py
```

Run a single scan:

```powershell
python main.py
```

---

## Backtesting

Backtesting can run inside scanner flow after final qualification.

Enable in `config.json`:

- `BACKTEST_ENABLED: true`
- `BACKTEST_REQUIRE_TARGET_EXCHANGE: false` (default: include all final-phase coins)
- Optional gate mode: `BACKTEST_REQUIRE_TARGET_EXCHANGE: true` and set `BACKTEST_EXCHANGES`

Data source behavior:

- Primary source for all symbols: CoinGecko OHLCV (`1h/4h/1d` when hourly available)
- Intraday fallback: Polygon hourly OHLCV
- Last-resort fallback: CoinGecko daily OHLC (`1d` only)

Run scanner:

```powershell
python main.py
```

Render ranked output and top settings from artifact:

```powershell
python scripts/render_backtest_report.py
```

Backtesting artifact:

- `backtest_results.json`

Operational recovery checklist:

- `docs/backtesting-runbook.md`

---

## Operations

Useful operational scripts in this repo:

- `scheduler.py` — scheduled scanner execution
- `manage_bot.py` — bot process management helpers
- `bot_watchdog.py` — process health monitoring/restarts
- `update_exchanges.py` — exchange listing refresh
- `update_mappings.py` — mapping refresh

Suggested cadence:

- Scanner: hourly
- Exchange listing refresh: weekly
- Mapping refresh: monthly
- Watchdog: every 5 minutes

---

## Logs and Outputs

- `trend_scanner.log` — full pipeline runtime log and summaries
- `bot_output.log` — Telegram/bot-side output
- `metrics.json` — persisted metrics snapshot

---

## Notes

- If Chart-IMG key is missing or unavailable, notifications can still use cached OHLCV fallback chart when present.
- If public CoinGecko limit pressure is high, scanner degrades gracefully using cache + fail-fast behavior on non-critical ticker fetches.
