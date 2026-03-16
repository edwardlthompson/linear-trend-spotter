# Linear Trend Spotter

Automated full-exchange scanner focused on identifying sustained trend quality (not one-candle pumps), with integrated multi-strategy backtesting to validate and rank opportunities before alerting.

## Key Features

1. **Trend Identification (Primary):** Evaluates the full exchange universe and identifies sustained, high-quality trends through strict multi-stage qualification.
2. **Integrated Backtesting (High-Value Validation):** Runs multi-strategy, multi-timeframe backtests only after trend qualification and ranks opportunities for alerts.
3. **Actionable Telegram Alerts:** Sends enriched entry/exit notifications and event-driven dashboard summaries (on entry/exit), with watchlist context.
4. **Resilient Data/Fallback Pipeline:** Uses CoinGecko-first data sourcing with fallback paths for continuity, enforcing strict OOM memory clipping for low-RAM remote deployments (e.g. Render Basic plans).
5. **Insights Layer:** Persists rank history, regime state, drift monitoring, outcome analytics, data reliability, and portfolio simulation.
6. **Deterministic TSL-Only Backtesting:** Deterministic backtesting engine optimizes with trailing stop loss only (no TP/TTP sweep) using bounded hill-climbing search for fast convergence.

[![Telegram Group](https://img.shields.io/badge/Telegram-Join%20Group-blue?logo=telegram)](https://t.me/+pmZewVhuEFJjYTIx)

---

## What It Does

Linear Trend Spotter scans all symbols listed across target exchanges (default: Coinbase, Kraken, MEXC), then applies a strict multi-step qualification pipeline:

1. Top-coin provider snapshot pull (`TOP_COINS_PROVIDER`, default `coingecko`, up to `TOP_COINS_LIMIT` coins)
2. Exchange listing universe build (all symbols in `exchange_listings`)
3. Gain/volume filter
4. CoinGecko ID mapping
5. Exchange-volume enrichment (CoinGecko tickers)
6. 30-day uniformity scoring from market chart history
7. **Backtesting stage (featured):** always-on multi-strategy, multi-timeframe backtests on final-stage qualified coins
8. Entry/exit detection vs active list
9. Telegram notifications (entry/exit + event summary image when entries/exits occur)
10. Insights persistence (`scanner_insights.json`)
11. History persistence + metrics/log summary

---

## Current Qualification Rules

Qualification determines which coins enter the **backtesting stage** and therefore which backtest-ranked strategy outputs are included in alerts.

### Filter 1: Volume + gains

- 24h provider volume must be `>= MIN_VOLUME_M` (default `1,000,000`)
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
  - Coin name/symbol with provider-aware source link
  - 7d and 30d gains
  - uniformity score
  - ATR score
  - health score
  - rank movement vs previous scan
  - volume acceleration vs recent daily baseline
  - total 24h provider volume
  - exchange-level volumes (Coinbase/Kraken/MEXC)
- Sends a single combined image when a chart is available:
  - **Price Line Chart (top):** Rendered with continuous line graphs including profitable/losing trade durations highlighted with Green/Red transparent background boxes, avoiding dot clutter. Automatically resamples data to match strategy timeframe accurate overlays.
  - Ranked backtest strategy table (bottom)
- Strategy rows are now confidence-weighted before choosing the top notification strategy.

Notification enhancement details:

- **Health score:** blends uniformity, rank, ATR, data reliability, volume acceleration, and strategy-confidence fallback.
- **Backtest confidence weighting:** top strategies are ranked by weighted net score instead of raw net % alone.
- **Data reliability:** reliability is derived from mapping/ticker/OHLCV source quality.

Example entry notification excerpt:

```text
🟢 DOGE (Dogecoin)

📊 Gains:
   7d: +12.4%
   30d: +48.7%

📈 Uniformity Score: 71/100
📏 ATR Score: 76/100 (ATR30: 2.40%)
🩺 Health Score: 79/100 (strong)

🏁 Rank: #3 ↑ from #8 (5)
🚀 Volume Acceleration: +37% vs prior 7d avg
```

### Exit notifications

- Sent once when a previously active coin leaves qualification.
- Includes precise exit reason (first failed stage), for example:
  - 24h volume below threshold
  - 30d threshold violation
  - `30d <= 7d`
  - missing top-coin provider or CoinGecko data
  - uniformity score below threshold
- Includes alert lifecycle P&L summary from active-state tracking:
  - realized/unrealized lifecycle P&L at exit
  - max run-up since entry
  - max drawdown since entry
  - hold duration in days
- Sends an exit dashboard image (image-first, text fallback) with:
  - top mini-chart feature using recent 1h candles
  - explicit entry and exit markers on chart
  - lifecycle + risk panel (reason, P&L/run-up/drawdown, held duration, health/uniformity)
  - market context panel (entry/exit price, 7d/30d gains, 24h volume, rank, on-list duration, cooldown)

### Event dashboard image + watchlist mode

- A compact event summary image is sent only when there is at least one entry or exit.
- Event summary shows:
  - regime + benchmark drift state
  - active rankings with health, gain since entry, and time-on-list
  - top watchlist near-qualifiers
- Watchlist mode captures near-qualifiers that narrowly miss final inclusion (uniformity/gain proximity).

### Event active ranking summary

- Sent only on scans where at least one entry or exit occurred.
- Includes all currently active qualified coins, ordered by current rank.
- Each row includes:
  - rank and movement arrow (`↑`, `↓`, `→`, `🆕`)
  - health score
  - percentage gain since first announcement (entry baseline)
  - on-list duration (`Xd Yh`)
- Active rank uses active-list order (`A#1`, `A#2`, ...), independent of non-active qualified rows.
- Runtime includes an explicit marker log line:
  - `📌 EVENT_SUMMARY_SENT messages=<sent>/<total> active_coins=<count>`

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
| `MIN_VOLUME_M` | `1000000` | Minimum 24h volume gate from selected top-coin provider |
| `TOP_COINS_PROVIDER` | `coingecko` | Top-coin universe source for Filter 1 (`coingecko` or `cmc`) |
| `TOP_COINS_LIMIT` | `4000` | Number of top-ranked coins pulled into Filter 1 |
| `COINGECKO_ID_ALIASES` | `{"CRYPGPT":"crypgpt"}` | Exchange symbol -> CoinGecko coin id fallback for tokens not present in `/coins/markets` paging |
| `UNIFORMITY_MIN_SCORE` | `55` | Uniformity filter cutoff |
| `ENTRY_NOTIFICATIONS` | `true` | Enable entry alerts |
| `EXIT_NOTIFICATIONS` | `true` | Enable exit alerts |
| `NO_CHANGE_NOTIFICATIONS` | `false` | Legacy no-change ping toggle |
| `ALERT_COOLDOWN_HOURS` | `6` | Re-entry cooldown window after exit |
| `CMC_SYMBOL_ALIASES` | `{"CRYPGPT":"CGPT"}` | Exchange-symbol to CMC-symbol fallback map used only when `TOP_COINS_PROVIDER` is `cmc` |

Notes:

- Runtime now treats the historical `cmc_url` database field as a generic source-link storage column for backward compatibility. Under CoinGecko-provider scans it stores the CoinGecko source URL instead of forcing a CoinMarketCap link.
- CoinGecko ID alias fallback is reused in both Filter 1 qualification and exit-reason attribution so symbols like `CRYPGPT` do not resolve one way on entry and another way on exit.
| `WATCHLIST_ENABLED` | `true` | Enable near-qualifier watchlist generation |
| `WATCHLIST_SCORE_BUFFER` | `8` | Uniformity proximity buffer used for watchlist inclusion |
| `PORTFOLIO_SIM_ENABLED` | `true` | Enable alert-following portfolio simulation state updates |
| `PORTFOLIO_SIM_STARTING_CAPITAL` | `10000` | Starting capital for portfolio simulation |
| `SCANNER_INSIGHTS_FILE` | `scanner_insights.json` | Combined insights artifact for dashboard, drift, outcomes, and simulation |
| `BACKTEST_ENABLED` | `true` | Always-on in runtime (value kept for compatibility; `false` is ignored) |
| `BACKTEST_REQUIRE_TARGET_EXCHANGE` | `false` | Gate backtests by `BACKTEST_EXCHANGES` when enabled |
| `BACKTEST_MAX_PARAM_COMBOS` | `100` | Max param combos per indicator/timeframe |
| `BACKTEST_PARALLEL_WORKERS` | `4` | Process workers for per-coin backtesting |
| `BACKTEST_PER_COIN_TIMEOUT_SECONDS` | `1800` | Per-coin watchdog timeout before pool fallback handling |
| `BACKTEST_TIMEFRAMES` | `['1h','4h']` | Backtest timeframes used by scanner |
| `BACKTEST_TRAILING_STOP_MIN` | `2` | Minimum trailing stop loss % |
| `BACKTEST_TRAILING_STOP_MAX` | `20` | Maximum trailing stop loss % |
| `BACKTEST_TRAILING_STOP_STEP` | `2` | Trailing stop step size (even-number sweep) |
| `BACKTEST_CHECKPOINT_FILE` | `backtest_checkpoint.json` | Incremental backtest checkpoint artifact |
| `BACKTEST_TELEMETRY_FILE` | `backtest_telemetry.jsonl` | Structured per-event backtest telemetry stream |
| `EXIT_ANALYTICS_FILE` | `exit_reason_analytics.json` | Cumulative exit-reason analytics artifact |
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

- Primary source for backtest timeframes: CoinGecko OHLCV (`1h/4h`)
- Intraday fallback: Polygon hourly OHLCV

Search behavior:

- Parameter optimization uses **coordinate-descent hill climbing** (start from midpoint defaults, test one-step up/down neighbors, keep improving direction).
- Optimization is **TSL-only** (`take_profit_pct=0`, `trailing_take_profit_pct=0`).
- Default TSL sweep uses even values: `2, 4, 6, ..., 20`.

Backtest fairness + result quality rules:

- Strategy runs start long on the first bar (same start posture as `B&H`)
- Strategy rows with win rate $< 70\%$ are filtered out before ranked output.
- Strategy rows with TSL Hit Frequency $> 50\%$ are filtered out.
- Strategy columns are reordered to group TSL settings metrics together: `TSL % | TSL Hits | TSL Hit %`.

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

Sanity verification profiles:

- **Strict verifier (CI / release gate):** requires broad symbol coverage and full pass threshold.

```powershell
python scripts/verify_backtest_data.py
```

- **Fast verifier (local smoke check):** bounded runtime with per-symbol timeout to avoid long API-backoff stalls.

```powershell
python scripts/verify_backtest_data.py --sanity --max-seconds 30 --per-symbol-timeout 5 --min-passed 0
```

Notes:

- `--sanity` bounds the run to a small symbol set for quick feedback.
- `--max-seconds` caps total runtime.
- `--per-symbol-timeout` isolates slow symbols so one fallback chain cannot block the full verifier.
- Use non-zero `--min-passed` when you want a quality threshold even in bounded mode.

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
