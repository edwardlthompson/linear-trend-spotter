# Linear Trend Spotter

A scanner that pulls exchange-listed coins, filters on volume and momentum, scores **OHLCV uniformity**, runs **integrated backtests**, and publishes results where you actually look at them: a **web dashboard** (GitHub Pages–friendly) plus optional **browser push**.

No chat-bot pipeline—configuration points at **`qualified_public_snapshot.json`**, optional **`snapshot_server`** relay on Render, and optional **Tier-B** (`push_server`) / **Tier-C** (ntfy) list-change notifications.

## Why use it

If you watch trends across majors like Coinbase, Kraken, or MEXC, manually screening thousands of pairs does not scale. This repo automates the boring gates (liquidity, sustained upside, cleaner candles), ranks what survives, and exposes sortable tables with sparklines, health scores, watchlists, and exports—without pulling browser clients into raw exchange APIs.

## What you get

- **Scanner worker:** scheduled runs (e.g. Render), SQLite caches, CoinGecko/CMC/Polygon as configured, anomaly hints in logs.
- **Qualified snapshot:** JSON consumed by the static UI under `docs/dashboard/`; relay POST optional.
- **Dashboard (static PWA):** sortable multi-venue table, **7d / 30d** sparklines from `closes_1h` (click a chart cell for a full-screen hourly plot), optional **per-chart % below high** filters on **7d** / **30d** chart headers, watchlist pins, CSV/JSON export, **List changes** bell + **Logs** tab badges (hidden when zero), theme toggle (**LTS** short name / **Linear Trend Spotter** full title in manifest), backtest **Results** modal with **TSL %** and **TSL hit %**, **Tier-A** poll alerts, **Tier-B** Web Push, **Tier-C** ntfy (FOSS off-device)—platform-aware notification guide on enable—see **`docs/WEB_DASHBOARD.md`**.
- **Backtesting:** per-coin strategy sweep artifacts (`backtest_results.json`, checkpoints)—library boundary documented in **`docs/BACKTESTING_LIBRARY.md`**.

## Quick start

1. **Python 3.11+** and [uv](https://docs.astral.sh/uv/): `uv sync --locked --extra dev` (add `--extra talib` for local prod with TA-Lib).
2. Copy **`.env.example`** → `.env`; set at least **`CMC_API_KEY`** (and optional **`COINGECKO_API_KEY`** for production-grade CoinGecko—still used for OHLCV, tickers, and the `/coins/list` id mapper).
3. Optional **`config.json`** from **`config.json.example`**—sensible defaults already live in **`config/settings.py`**.
4. Run **`uv run python main.py`** (or your scheduler) from repo root; snapshot lands under **`DATA_DIR`** / **`qualified_public_snapshot.json`** when enabled.

**API budget:** defaults use **`TOP_COINS_PROVIDER`: `"cmc"`** so the **ranked universe** comes from **one** CoinMarketCap `listings/latest` call per scan instead of many CoinGecko `/coins/markets` pages. CoinGecko ids for OHLCV and exchange tickers are resolved via the local mapper (including **name-aware** matching when CMC supplies symbol + name). To spend CoinGecko credits last on hourly bars, set **`OHLCV_UNIFORMITY_SOURCE_ORDER`** (e.g. `cmc,polygon,coingecko`)—see **`docs/COIN_API_CREDIT_STRATEGY.md`**.

**Live dashboard JSON:** set **`QUALIFIED_SNAPSHOT_RELAY_URL`** + **`QUALIFIED_SNAPSHOT_RELAY_SECRET`** on the worker and deploy **`snapshot_server/`** (see **`render.yaml`** fragment).

**Tier-C ntfy (optional):** after setting **`RENDER_API_KEY`**, run `python scripts/provision_tier_c_ntfy.py --generate --apply --dashboard-url https://…` — the worker publishes list-change alerts; the public snapshot exposes `notify_public_config.ntfy_subscribe_url` for the dashboard guide. See **`docs/MANUAL_DEPLOY_STEPS.md`** §7.

**Local dashboard preview:** `cd docs/dashboard && python -m http.server 8765` and open with **`?api=`** pointing at your relay URL—details in **`docs/WEB_DASHBOARD.md`**.

## Repo layout (short)

| Path | Role |
|------|------|
| `main.py` | Scan orchestration |
| `scanner/` | Pipeline stages (filters, listings, uniformity, web push + ntfy hooks) |
| `docs/dashboard/` | Static PWA UI |
| `snapshot_server/` | Small Flask relay for public GET + worker POST |
| `push_server/` | Optional Web Push relay (Tier-B) |
| `clients/windows/` | FOSS tray notifier scaffold + winget manifest |
| `clients/android/` | UnifiedPush companion scaffold + F-Droid metadata |
| `scripts/provision_tier_c_ntfy.py` | Automate `NTFY_*` on Render worker |
| `scripts/check_snapshot_relay.py` | Operator tool: GET `/relay-health`, optional ingest smoke test (env `QUALIFIED_SNAPSHOT_RELAY_*`) |
| `scripts/check_exchange_print_ascii.py` | CI guardrail: `exchange_data` `print()` lines must be ASCII (Windows console safety) |

## Docs index

- **`linear-trend-spotter-spec.md`** — technical specification (architecture and behavior)  
- **`docs/EXECUTION_PLAN.md`** — engineering milestones and file map  
- **`docs/DELIVERY_MODE.md`** — how snapshot data reaches the browser  
- **`docs/MANUAL_DEPLOY_STEPS.md`** — Render / Pages checklist  
- **`docs/render-setup.md`** — Render blueprint and worker notes  
- **`docs/WEB_DASHBOARD.md`** — dashboard UI (grid, per-chart filters, Tier-A/B/C alerts, notification guide), relay/env vars
- **`docs/PRIVACY.md`** — privacy policy draft (Web Push + ntfy)  
- **`docs/COIN_API_CREDIT_STRATEGY.md`** — splitting load across CoinGecko / CoinMarketCap / Polygon, **rate limits & backoff**, **bulk `/coins/markets`** alias fetching  
- **`docs/API_MONTHLY_BUDGET_ESTIMATE.md`** — rough monthly HTTP estimates per provider  
- **`docs/API_PROVIDER_DEEP_ANALYSIS.md`** — which API fits which pipeline stage  
- **`docs/CROSS_PROVIDER_IDENTITY.md`** — translating ids/slugs across vendors; **`identity`** on qualified snapshot rows  

Optional **`config.json`** keys include **`TOP_COINS_PROVIDER`** (`cmc` or `coingecko`), **`OHLCV_UNIFORMITY_SOURCE_ORDER`**, **`COINGECKO_CALLS_PER_MINUTE`**, **`CMC_CALLS_PER_MINUTE`**, **`POLYGON_CALLS_PER_MINUTE`** (see **`config.json.example`**).

## Contributing / CI

`scripts/ci_verify.sh` is the same command Render’s **worker** runs at build time (`uv sync --locked --extra dev`, then **ruff**, **mypy**, **pytest**, etc.). Legacy **`requirements*.txt`** files are exported from **`uv.lock`** for reference only.

**Agent bootstrap:** read `docs/START_HERE.md` and `AGENTS.md`. Task boards: `BUILD_PLAN.md` (ops) and `docs/EXECUTION_PLAN.md` (product). BUILD_PLAN labels: `AGENT` | `HUMAN` | `AUTO`.

**Template updates:** configure interval in `.template-update.json`; manual check: `pwsh scripts/check-template-updates.ps1`.

**Required GitHub workflows after push to `main`:** CI, Security Scan, CodeQL — poll with `python scripts/check_github_ci.py --wait 300`.

See **`CONTRIBUTING.md`**, **`SECURITY.md`**, and **`docs/SECURITY_TRIAGE.md`**.

**Production diagnostics:** if the dashboard looks empty but the worker ran, check the snapshot relay (`scripts/check_snapshot_relay.py` from a shell that has relay env vars, or open `/relay-health` on the relay host). Worker logs may show **`EXCHANGE_UNIVERSE_FALLBACK`** when exchange listings never populated—often a failed listings refresh (see `exchange_data` logs).

PRs should keep **`python scripts/check_github_ci.py`** green if you use that helper.
