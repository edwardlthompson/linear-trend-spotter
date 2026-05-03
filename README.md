# Linear Trend Spotter

Automated full-exchange scanner focused on identifying sustained trend quality (not one-candle pumps), with integrated multi-strategy backtesting to validate and rank opportunities before alerting.

**Default delivery** is the **public qualified dashboard** (snapshot JSON + GitHub Pages UI); Telegram alerts are **optional** (`DELIVERY_MODE`). See [`docs/DELIVERY_MODE.md`](docs/DELIVERY_MODE.md) and [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md).

## Key Features

1. **Trend Identification (Primary):** Evaluates the full exchange universe and identifies sustained, high-quality trends through strict multi-stage qualification.
2. **Integrated Backtesting (High-Value Validation):** Runs multi-strategy, multi-timeframe backtests only after trend qualification and ranks opportunities for alerts.
3. **Qualified dashboard & alerts:** Read-only **PWA** with snapshot-driven tables, optional Tier-A/Tier-B notifications; **optional Telegram** entry/exit messaging when `DELIVERY_MODE` is `telegram`.
4. **Resilient Data/Fallback Pipeline:** Uses CoinGecko-first data sourcing with fallback paths for continuity, enforcing strict OOM memory clipping for low-RAM remote deployments (e.g. Render Basic plans).
5. **Insights Layer:** Persists rank history, outcome analytics, data reliability, and portfolio simulation.
6. **Deterministic TSL-Only Backtesting:** Deterministic backtesting engine optimizes with trailing stop loss only (no TP/TTP sweep) using bounded hill-climbing search for fast convergence.

[![Telegram Group](https://img.shields.io/badge/Telegram-Join%20Group-blue?logo=telegram)](https://t.me/+pmZewVhuEFJjYTIx)
[![CI](https://github.com/edwardlthompson/linear-trend-spotter/actions/workflows/ci.yml/badge.svg)](https://github.com/edwardlthompson/linear-trend-spotter/actions/workflows/ci.yml)

**Repository:** [github.com/edwardlthompson/linear-trend-spotter](https://github.com/edwardlthompson/linear-trend-spotter)

---

## Public qualified-coin dashboard (website)

Read-only **PWA** for the hourly qualified snapshot: sort, filter, theme, exports, deep links, optional chart thumbnails, scan health strip, in-browser “update alerts,” and optional **Tier-B Web Push** when you deploy the small relay service.

**Live site (GitHub Pages, after you turn Pages on):** [edwardlthompson.github.io/linear-trend-spotter/dashboard/](https://edwardlthompson.github.io/linear-trend-spotter/dashboard/)

If that URL returns **404**, GitHub Pages is not publishing from **`/docs`** yet (or the first deploy is still running—wait 1–2 minutes and hard-refresh). See **step 3** below and the **404 checklist** right after it. Full behavior and CORS notes live in [`docs/WEB_DASHBOARD.md`](docs/WEB_DASHBOARD.md).

**You do not need GitHub Pages.** Pick what matches how you want to work:

| Goal | What to do |
|------|------------|
| **Alerts and summaries in Telegram only** | Defaults are Telegram-first (`config.json.example`, **`render.yaml`** worker, **`config/settings.py`**). Set **`TELEGRAM_BOT_TOKEN`** and **`TELEGRAM_CHAT_ID`** on Render (or `.env` locally). Override with **`DELIVERY_MODE=web`** if you want dashboard-only delivery — [`docs/DELIVERY_MODE.md`](docs/DELIVERY_MODE.md). |
| **Table-style dashboard on this PC only** | After a scan writes `qualified_public_snapshot.json` under your **`DATA_DIR`**, run **`python scripts/local_dashboard.py`** — opens a browser at `http://127.0.0.1:8765/dashboard/` using your local JSON (no git push, no Render relay). |
| **Public website on github.io** | Use **Option A** below (`sync_snapshot_to_docs.py` + push). |

**404 checklist**

| Fix | Where |
|-----|--------|
| Turn Pages on | Repo **Settings → Pages** → **Build and deployment** → **Source:** branch **`main`**, folder **`/docs`** (not “`/ (root)`”). Save. |
| Confirm the deploy | Same **Pages** page: wait until it shows a green success or a **`your-branch`** publish notice; then open the site again. |
| Wrong URL | Project Pages live at **`https://edwardlthompson.github.io/linear-trend-spotter/`** plus paths under `docs/`. The dashboard is **`…/dashboard/`** (maps to `docs/dashboard/index.html`). |
| Repo visibility | **Public** repos get free Pages on github.io; **private** repos may need GitHub Pro/Team for Pages (otherwise enable Pages only works on public mirrors). |

### How to enable the dashboard

**Option A — GitHub Pages + JSON in this repo (simplest, no Render relay for the site)**  
The static site can load a file **from the same GitHub repository** so there is **no CORS** and no extra host to wire up for the read-only list.

1. **Turn on GitHub Pages**  
   **Settings → Pages** → **Source:** branch **`main`**, folder **`/docs`**. The site is at  
   `https://edwardlthompson.github.io/linear-trend-spotter/dashboard/`.

2. **Publish `docs/qualified_public_snapshot.json`**  
   Committed default is a tiny placeholder (empty `coins`). After you run a scan locally (or wherever `qualified_public_snapshot.json` is written under `DATA_DIR`):

   ```bash
   python scripts/sync_snapshot_to_docs.py
   git add docs/qualified_public_snapshot.json
   git commit -m "Update qualified snapshot for Pages"
   git push
   ```

   Wait ~1–2 minutes for Pages to rebuild; hard-refresh the dashboard.

3. **Dashboard URL**  
   [`docs/dashboard/config.js`](docs/dashboard/config.js) defaults to **`../qualified_public_snapshot.json`** (same origin). No secrets in that file.

**Option B — Render snapshot relay (optional)**  
If you want the JSON updated from a **Render worker** without committing files, deploy **`snapshot_server/`** from [`render.yaml`](render.yaml), set **`QUALIFIED_SNAPSHOT_RELAY_*`** on worker + relay service, and point **`window.__SNAPSHOT_URL__`** (or **`?api=`**) at `https://<your-snapshot-service>.onrender.com/qualified_public_snapshot.json`. See [`docs/WEB_DASHBOARD.md`](docs/WEB_DASHBOARD.md) for CORS and cache notes.

**Optional: Tier-B Web Push (off-device scan alerts)**  
Deploy **`push_server/`** from [`render.yaml`](render.yaml), set worker **`WEB_PUSH_*`** env vars, and add **`__PUSH_API_BASE__`** / **`__VAPID_PUBLIC_KEY__`** to dashboard `config.js` per [`docs/WEB_DASHBOARD.md`](docs/WEB_DASHBOARD.md).

---

## Recent engineering additions (changelog-style)

Release announcements with dates: **[`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md)**.

| Area | What shipped |
|------|----------------|
| **Public dashboard (Q)** | Static `docs/dashboard/` PWA: snapshot-driven table, health strip (**Q20**), Tier-A polling alerts, Tier-B Web Push client (**Q21**), docs in `docs/WEB_DASHBOARD.md`. |
| **Web Push relay (Q21)** | Optional `push_server/` Flask + `pywebpush`; second service in `render.yaml`; worker calls relay after each successful scan when env vars are set. |
| **Snapshot relay (Q4+)** | Optional `snapshot_server/` Flask; third web service in `render.yaml`; worker POSTs JSON after each scan when `QUALIFIED_SNAPSHOT_RELAY_*` are set so GitHub Pages can `GET` the file with CORS. |
| **Web-first default (2026-05)** | Repo defaults: **`DELIVERY_MODE`** **`web`**, **`TELEGRAM_ENABLED`** **`false`**, public snapshot **on** in `config.json.example`; Render blueprint matches. See [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md). |
| **Backtesting library (P2)** | `backtesting/params.py` — inject **`BacktestLoaderParams`** / **`BacktestRunnerParams`** so hosts avoid the full `settings` object; lazy exports in `backtesting/__init__.py`. |
| **CI / tests** | `tests/conftest.py` redirects read-only **`DATA_DIR=/var/data`** during pytest collection on Render-style builds. |

### Delivery mode (current default: web / dashboard)

Canonical reference: **[`docs/DELIVERY_MODE.md`](docs/DELIVERY_MODE.md)**.

The repository **defaults** to **`DELIVERY_MODE`** **`web`** and **`TELEGRAM_ENABLED`** **`false`** (`config/settings.py`, `config.json.example`, **`render.yaml`** worker env). The scanner **does not** initialize the Telegram client; **`scripts/run_render_worker.sh`** does **not** start **`telegram_bot.py`**. Use the **[qualified dashboard](#public-qualified-coin-dashboard-website)** with **`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`** and the **[snapshot relay](#how-to-enable-the-dashboard)** (`snapshot_server/`) so GitHub Pages can load JSON.

**Switching back to Telegram:** set **`DELIVERY_MODE`** to **`telegram`**, **`TELEGRAM_ENABLED`** to **`true`**, set **`TELEGRAM_BOT_TOKEN`** and **`TELEGRAM_CHAT_ID`**, redeploy, and ensure the worker environment matches (see `docs/RELEASE_NOTES.md` for a short checklist).

Routine “Telegram skipped” startup detail is logged at **DEBUG** when delivery is web-only.

---

## CI and deployment

- **GitHub Actions & Render build parity:** Both run **`bash scripts/ci_verify.sh`**, which installs **`requirements-ci.txt`** (no **`TA-Lib`** sdist; **`numpy<2`** like CI), **`ruff`**, then runs **`ruff check .`**, **`python scripts/verify_backtest_env.py`**, and **`python -m compileall -q .`**. The canonical full dependency list (including **TA-Lib** for local installs) stays in **`requirements.txt`** (UTF-8); use `pip install -r requirements.txt` on a machine or image with native TA-Lib headers when you need compiled indicators locally.
- **Docker Compose (M3):** From the repo root, `docker compose config` validates **`docker-compose.yml`**. Run `docker compose run --rm app` for a quick CI-parity smoke (Ruff, import guard, `verify_backtest_env`, `compileall`) inside **`python:3.11-bookworm`** — optional; Render still uses **`render.yaml`**.
- **Milestone gate:** Before treating a milestone as done (per `docs/EXECUTION_PLAN.md`), confirm **`main`** CI is green and the Render worker deploy for the same commit is **live** when you rely on auto-deploy; locally run `python scripts/check_github_ci.py` (needs `gh auth login` or `GITHUB_TOKEN` with Actions read).
- **Render:** The worker uses `render.yaml` with `autoDeployTrigger: commit` so merges to the connected branch trigger a deploy. In the Render dashboard, confirm the service is linked to this repository, the correct **branch**, and **Auto-Deploy** is on (see execution plan milestone **A1**).
- **Render API (snapshot relay env):** With a personal **[API key](https://dashboard.render.com/u/settings#api-keys)** in **`RENDER_API_KEY`**, you can run **`python scripts/render_snapshot_relay_env.py --dry-run`** (then **`--apply --generate-secret`** or **`--apply --secret …`**) to set **`QUALIFIED_SNAPSHOT_RELAY_URL`** / **`QUALIFIED_SNAPSHOT_RELAY_SECRET`** on the worker and snapshot services. Read the script docstring for limits (PUT replaces all env vars; masked secrets need care). **`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`** still must be set in **`config.json`** on the worker.
- **`TOP_COINS_PROVIDER` on Render:** Set `TOP_COINS_PROVIDER=cmc` in `config.json` (or mount the same file) to pull **top-coin / listing** metadata from CoinMarketCap while **OHLCV stays CoinGecko → Polygon → CoinMarketCap** (`main.py` / `backtesting/data_loader.py`). Requires `CMC_API_KEY` and (for fallbacks) `POLYGON_API_KEY` as today. Default remains `coingecko` if unset.
- **Branch protection:** After CI is green, enable required status checks on `main` so merges cannot bypass the workflow (milestone **A4** in `docs/EXECUTION_PLAN.md`).
- **Engineering roadmap:** `docs/EXECUTION_PLAN.md` tracks milestones, verification steps, and checkbox progress.
- **Exception hygiene:** `scheduler.py`, `manage_bot.py`, and `bot_watchdog.py` use specific exception handling (no bare `except:`) where lock files, PIDs, and subprocess fallbacks are involved.
- **Telegram safety (milestone C):** Long-polling and Bot API helpers check HTTP status before parsing JSON, handle `JSONDecodeError`, and escape user- or API-derived text in **HTML** captions (`html.escape` / formatter helpers).
- **Cross-platform (milestone E):** The scan scheduler uses **`portalocker`** instead of `fcntl`, so imports work on Windows dev machines as well as Linux. `manage_bot.py` / `bot_watchdog.py` use **`sys.executable`** (no hard-coded `python3`); log tailing avoids a `tail` subprocess.
- **Tooling (milestone D):** `pyproject.toml` configures **Ruff** for a narrow rule set (`E9`, `F`) so CI catches syntax and import issues without noisy style churn. `requirements.txt` uses **compatible-release** upper bounds on major versions.
- **Logging (milestone F):** `config/settings.py`, `database/cache.py`, `utils/metrics.py`, and `utils/rate_limiter.py` use standard **`logging`**; CLI scripts under `scripts/` may still use `print` (documented in `utils/logger.py`).
- **Telegram links (milestone G):** Entry headers, exit lines, inline “Analyze Coin” buttons, and history `source_url` prefer **CoinMarketCap** (`/currencies/{slug}/` or symbol search) when a real CMC slug exists; CoinGecko remains the data API and fallback link when CMC cannot be inferred.

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

- **Health score:** blends uniformity, rank, data reliability, volume acceleration, and strategy-confidence fallback.
- **Backtest confidence weighting:** top strategies are ranked by weighted net score instead of raw net % alone.
- **Data reliability:** reliability is derived from mapping/ticker/OHLCV source quality.

Example entry notification excerpt:

```text
🟢 DOGE (Dogecoin)

📊 Gains:
   7d: +12.4%
   30d: +48.7%

📈 Uniformity Score: 71/100
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

### Event dashboard image

- A compact event summary image is sent only when there is at least one entry or exit.
- Event summary shows:
  - active rankings with health, gain since entry, and time-on-list

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

Telegram bot runtime mode (`telegram_bot.py`):

- Default **polling** mode (Render-friendly): set `TELEGRAM_BOT_MODE` to `polling` (or leave unset).
- Optional **webhook** mode: set `TELEGRAM_BOT_MODE` to `webhook` and configure:
  - `TELEGRAM_WEBHOOK_URL` (public HTTPS base, no trailing path, e.g. `https://example.com`)
  - `TELEGRAM_WEBHOOK_PATH` (default `/telegram/webhook`)
  - `TELEGRAM_WEBHOOK_PORT` (default `8080`)
  - `TELEGRAM_WEBHOOK_SECRET_TOKEN` (optional, validated from `X-Telegram-Bot-Api-Secret-Token`)
- Polling mode automatically calls Telegram `deleteWebhook` to preserve legacy behavior.

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
- `scanner_insights.json` — rank persistence, outcomes, and portfolio simulation

---

## Notes

- If Chart-IMG key is missing or unavailable, notifications can still use cached OHLCV fallback chart when present.
- If public CoinGecko limit pressure is high, scanner degrades gracefully using cache + fail-fast behavior on non-critical ticker fetches.
