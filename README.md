# Linear Trend Spotter

Automated full-exchange scanner focused on identifying sustained trend quality (not one-candle pumps), with integrated multi-strategy backtesting to validate and rank opportunities before alerting.

## Key Features

1. **Trend Identification (Primary):** Evaluates the full exchange universe and identifies sustained, high-quality trends through strict multi-stage qualification.
2. **Integrated Backtesting (High-Value Validation):** Runs multi-strategy, multi-timeframe backtests only after trend qualification and ranks opportunities for alerts.
3. **Actionable Telegram Alerts:** Sends enriched entry/exit notifications, early warnings, watchlist summaries, and hourly dashboard images.
4. **Resilient Data/Fallback Pipeline:** Uses CoinGecko-first data sourcing with fallback paths for continuity.
5. **Insights Layer:** Persists rank history, regime state, drift monitoring, outcome analytics, data reliability, and portfolio simulation.

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
7. **Backtesting stage (featured):** always-on multi-strategy, multi-timeframe backtests on final-stage qualified coins
8. Entry/exit detection vs active list
9. Telegram notifications (entry/exit, watchlist, early warning, hourly summary image)
10. Insights persistence (`scanner_insights.json`)
11. History persistence + metrics/log summary

---

## Current Qualification Rules

Qualification determines which coins enter the **backtesting stage** and therefore which backtest-ranked strategy outputs are included in alerts.

### Filter 1: Volume + gains

- 24h CMC volume must be `>= MIN_VOLUME_M` (default `1,000,000`)
- 7d gain must be `> 7%`
- 30d gain must be `> 30%`
- 30d gain must be strictly higher than 7d gain (`30d > 7d`)
- Stablecoins are excluded

### Filter 2: Uniformity

- Uses 30-day **OHLCV-derived** daily bars (hourly aggregation)
- Primary source: CoinGecko hourly OHLCV
- Fallback source: Polygon hourly OHLCV
- Computes an OHLCV-aware uniformity score from 0–100 (trend + candle-structure stability)
- Must pass `UNIFORMITY_MIN_SCORE` (default `55`)
- Must also have positive 30d return

---

## Notification Behavior

### Entry notifications

- Sent once when a coin newly enters qualified state.
- Includes:
  - Coin name/symbol with CMC link
  - 7d and 30d gains
  - uniformity score
  - ATR score
  - health score
  - exchange-quality score
  - data-reliability score
  - re-entry quality label/score
  - rank movement vs previous scan
  - signal age for the top-ranked strategy
  - backtest confidence for the top-ranked strategy
  - volume acceleration vs recent daily baseline
  - total 24h CMC volume
  - exchange-level volumes (Coinbase/Kraken/MEXC)
- Sends a single combined image when a chart is available:
  - price chart (top)
  - ranked backtest strategy table (bottom)
- Strategy rows are now confidence-weighted before choosing the top notification strategy.

Notification enhancement details:

- **Health score:** blends rank, uniformity, ATR, exchange quality, data reliability, volume acceleration, and top-strategy confidence.
- **Backtest confidence weighting:** top strategies are ranked by weighted net score instead of raw net % alone.
- **Re-entry quality:** re-entering symbols are labeled/penalized based on recent exit churn.
- **Exchange quality:** final qualification now includes an exchange-quality filter based on target exchange breadth and liquidity concentration.
- **Data reliability:** coins receive a reliability score from mapping/ticker/OHLCV source quality.

Example entry notification excerpt:

```text
🟢 DOGE (Dogecoin)

📊 Gains:
   7d: +12.4%
   30d: +48.7%

📈 Uniformity Score: 71/100
📏 ATR Score: 76/100 (ATR14: 2.40%)
🩺 Health Score: 79/100 (strong)
🏦 Exchange Quality: 67/100 (solid)
🧪 Data Reliability: 84/100 (high)

🏁 Rank: #3 ↑ from #8 (5)
⏱️ Best Strategy Signal: RSI • 2 candles ago on 4h (~8h)
🧠 Backtest Confidence: 73/100 (weighted net: +31.25)
🔁 Re-entry Quality: 100/100 (fresh)
🌦️ Regime: constructive
🚀 Volume Acceleration: +37% vs prior 7d avg
```

### Exit notifications

- Sent once when a previously active coin leaves qualification.
- Includes precise exit reason (first failed stage), for example:
  - 24h volume below threshold
  - 7d / 30d threshold violation
  - `30d <= 7d`
  - missing CMC / CoinGecko data
  - uniformity score below threshold
- Includes alert lifecycle P&L summary from active-state tracking:
  - realized/unrealized lifecycle P&L at exit
  - max run-up since entry
  - max drawdown since entry
  - hold duration in days

### Exit early-warning alerts

- Active coins can emit warning alerts before full exit when they are near failure thresholds.
- Warning conditions include:
  - volume near minimum threshold
  - softening 7d / 30d gain profile
  - shrinking `30d - 7d` spread
  - uniformity nearing cutoff
  - sharp rank deterioration
  - weak health score

### Hourly dashboard image + watchlist mode

- Every scan can send a compact hourly summary image showing:
  - regime + benchmark drift state
  - top active rankings with health and gain deltas
  - top watchlist near-qualifiers
- Watchlist mode captures near-qualifiers that narrowly miss final inclusion, especially on uniformity or exchange-quality thresholds.

### Per-scan active ranking summary

- Sent on every scan when Telegram is enabled.
- Includes all currently active qualified coins, ordered by current rank.
- Each row includes:
  - rank and movement arrow (`↑`, `↓`, `→`, `🆕`)
  - health score
  - percentage gain since first announcement (entry baseline)
  - percentage gain since the prior hourly update (previous active-state price baseline)
- Long lists are chunked into multiple Telegram messages to stay within message-size limits.
- Runtime includes an explicit marker log line:
  - `📌 ACTIVE_RANKING_SUMMARY_SENT messages=<sent>/<total> active_coins=<count>`

### Cooldown re-entry policy

- Exited symbols enter a cooldown window (`ALERT_COOLDOWN_HOURS`, default `6`).
- Symbols still in cooldown are blocked from immediate re-entry alerts.
- Blocked re-entries are logged in scanner runtime output for visibility.

### Weekly digest + anomaly detector

- **Weekly digest:** optional Telegram digest with 7-day operational stats, recurring symbols, entry/exit activity, and score summary.
- **Anomaly detector:** optional runtime anomaly alerting for:
  - excessive CoinGecko mapping miss ratio
  - excessive no-ticker ratio
  - low OHLCV success ratio

### Insights artifact

The scanner persists a multi-feature insights artifact in `scanner_insights.json` with:

- rank persistence dashboard history
- regime detection snapshot
- benchmark drift monitor history/status
- watchlist candidates
- exit early-warning rows
- post-alert outcome analytics
- portfolio simulation state
- low-reliability symbol summaries

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
| `UNIFORMITY_MIN_SCORE` | `55` | Uniformity filter cutoff |
| `ENTRY_NOTIFICATIONS` | `true` | Enable entry alerts |
| `EXIT_NOTIFICATIONS` | `true` | Enable exit alerts |
| `NO_CHANGE_NOTIFICATIONS` | `false` | Legacy no-change ping toggle |
| `ALERT_COOLDOWN_HOURS` | `6` | Re-entry cooldown window after exit |
| `CMC_SYMBOL_ALIASES` | `{"CRYPGPT":"CGPT"}` | Exchange-symbol to CMC-symbol fallback map used when direct CMC symbol lookup fails |
| `EXCHANGE_QUALITY_MIN_SCORE` | `25` | Minimum exchange-quality score to pass final qualification |
| `EARLY_WARNING_ENABLED` | `true` | Enable pre-exit warning alerts |
| `WATCHLIST_ENABLED` | `true` | Enable near-qualifier watchlist generation |
| `WATCHLIST_SCORE_BUFFER` | `8` | Uniformity proximity buffer used for watchlist inclusion |
| `PORTFOLIO_SIM_ENABLED` | `true` | Enable alert-following portfolio simulation state updates |
| `PORTFOLIO_SIM_STARTING_CAPITAL` | `10000` | Starting capital for portfolio simulation |
| `HOURLY_SUMMARY_IMAGE_ENABLED` | `true` | Enable hourly dashboard image sends |
| `SCANNER_INSIGHTS_FILE` | `scanner_insights.json` | Combined insights artifact for dashboard, drift, outcomes, and simulation |
| `BACKTEST_ENABLED` | `true` | Always-on in runtime (value kept for compatibility; `false` is ignored) |
| `BACKTEST_REQUIRE_TARGET_EXCHANGE` | `false` | Gate backtests by `BACKTEST_EXCHANGES` when enabled |
| `BACKTEST_MAX_PARAM_COMBOS` | `100` | Max param combos per indicator/timeframe |
| `BACKTEST_PARALLEL_WORKERS` | `4` | Process workers for per-coin backtesting |
| `BACKTEST_CHECKPOINT_FILE` | `backtest_checkpoint.json` | Incremental backtest checkpoint artifact |
| `BACKTEST_TELEMETRY_FILE` | `backtest_telemetry.jsonl` | Structured per-event backtest telemetry stream |
| `EXIT_ANALYTICS_FILE` | `exit_reason_analytics.json` | Cumulative exit-reason analytics artifact |
| `WEEKLY_DIGEST_ENABLED` | `true` | Enable weekly Telegram digest |
| `ANOMALY_ALERTS_ENABLED` | `true` | Enable anomaly detector notifications |
| `ANOMALY_MAX_MISSING_CG_RATIO` | `0.35` | Alert threshold for high CoinGecko mapping misses |
| `ANOMALY_MIN_OHLCV_SUCCESS_RATIO` | `0.60` | Alert threshold for low OHLCV processing success |
| `ANOMALY_MAX_NO_TICKER_RATIO` | `0.50` | Alert threshold for high no-ticker responses |
| `WEEKLY_DIGEST_ENABLED` | `true` | Enable weekly Telegram digest |
| `WEEKLY_DIGEST_WEEKDAY_UTC` | `0` | UTC weekday for digest send (`0=Monday`) |
| `WEEKLY_DIGEST_HOUR_UTC` | `12` | UTC hour for digest send |
| `WEEKLY_DIGEST_STATE_FILE` | `weekly_digest_state.json` | State file preventing duplicate weekly sends |

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

Backtesting runs inside scanner flow after final qualification.

Configure in `config.json`:

- `BACKTEST_ENABLED: true` (always enforced at runtime; `false` is ignored)
- `BACKTEST_REQUIRE_TARGET_EXCHANGE: false` (default: include all final-phase coins)
- Gate mode (still supported): `BACKTEST_REQUIRE_TARGET_EXCHANGE: true` and set `BACKTEST_EXCHANGES`

Data source behavior:

- Primary source for all symbols: CoinGecko OHLCV (`1h/4h/1d` when hourly available)
- Intraday fallback: Polygon hourly OHLCV
- Last-resort fallback: CoinGecko daily OHLC (`1d` only)

Backtest fairness + result quality rules:

- Strategy runs start long on the first bar (same start posture as `B&H`)
- Strategy rows with `win_pct <= 50.0` are filtered out before ranked output

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
- `backtest_checkpoint.json` (when resume is enabled)
- `backtest_telemetry.jsonl` (structured telemetry)

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
- `exit_reason_analytics.json` — cumulative exit reason breakdowns
- `scanner_insights.json` — rank persistence, watchlist, drift, outcomes, and portfolio simulation

---

## Notes

- If Chart-IMG key is missing or unavailable, notifications can still use cached OHLCV fallback chart when present.
- If public CoinGecko limit pressure is high, scanner degrades gracefully using cache + fail-fast behavior on non-critical ticker fetches.
