# Linear Trend Spotter

A scanner that pulls exchange-listed coins, filters on volume and momentum, scores **OHLCV uniformity**, runs **integrated backtests**, and publishes results where you actually look at them: a **web dashboard** (GitHub Pages–friendly) plus optional **browser push**.

No chat-bot pipeline—configuration points at **`qualified_public_snapshot.json`**, optional **`snapshot_server`** relay on Render, and optional Tier-B **`push_server`** for list-change notifications.

## Why use it

If you watch trends across majors like Coinbase, Kraken, or MEXC, manually screening thousands of pairs does not scale. This repo automates the boring gates (liquidity, sustained upside, cleaner candles), ranks what survives, and exposes sortable tables with sparklines, health scores, watchlists, and exports—without pulling browser clients into raw exchange APIs.

## What you get

- **Scanner worker:** scheduled runs (e.g. Render), SQLite caches, CoinGecko/CMC/Polygon as configured, anomaly hints in logs.
- **Qualified snapshot:** JSON consumed by the static UI under `docs/dashboard/`; relay POST optional.
- **Dashboard:** sortable multi-venue table, **7d / 30d** sparklines from `closes_1h` (click a chart cell for a full-screen hourly plot—distinct styling for 7d vs 30d), optional **per-chart % below high** filters on **7d chart** and **30d chart** headers (each excludes rows independently using that window’s distance-from-high), watchlist pins, CSV/JSON export, **List changes** bell feed with a **timestamp on each line**, Tier-A poll alerts, Tier-B push—see **`docs/WEB_DASHBOARD.md`**.
- **Backtesting:** per-coin strategy sweep artifacts (`backtest_results.json`, checkpoints)—library boundary documented in **`docs/BACKTESTING_LIBRARY.md`**.

## Quick start

1. **Python 3.11+**, `pip install -r requirements.txt` (use **`requirements-ci.txt`** where CI does).
2. Copy **`.env.example`** → `.env`; set at least **`CMC_API_KEY`** (and optional **`COINGECKO_API_KEY`** for production-grade CoinGecko).
3. Optional **`config.json`** from **`config.json.example`**—sensible defaults already live in **`config/settings.py`**.
4. Run **`python main.py`** (or your scheduler) from repo root; snapshot lands under **`DATA_DIR`** / **`qualified_public_snapshot.json`** when enabled.

**Live dashboard JSON:** set **`QUALIFIED_SNAPSHOT_RELAY_URL`** + **`QUALIFIED_SNAPSHOT_RELAY_SECRET`** on the worker and deploy **`snapshot_server/`** (see **`render.yaml`** fragment).

**Local dashboard preview:** `cd docs/dashboard && python -m http.server 8765` and open with **`?api=`** pointing at your relay URL—details in **`docs/WEB_DASHBOARD.md`**.

## Repo layout (short)

| Path | Role |
|------|------|
| `main.py` | Scan orchestration |
| `scanner/` | Pipeline stages (filters, listings, uniformity, web push hook) |
| `docs/dashboard/` | Static PWA UI |
| `snapshot_server/` | Small Flask relay for public GET + worker POST |
| `push_server/` | Optional Web Push relay |
| `scripts/check_snapshot_relay.py` | Operator tool: GET `/relay-health`, optional ingest smoke test (env `QUALIFIED_SNAPSHOT_RELAY_*`) |
| `scripts/check_exchange_print_ascii.py` | CI guardrail: `exchange_data` `print()` lines must be ASCII (Windows console safety) |

## Docs index

- **`linear-trend-spotter-spec.md`** — technical specification (architecture and behavior)  
- **`docs/EXECUTION_PLAN.md`** — engineering milestones and file map  
- **`docs/DELIVERY_MODE.md`** — how snapshot data reaches the browser  
- **`docs/MANUAL_DEPLOY_STEPS.md`** — Render / Pages checklist  
- **`docs/render-setup.md`** — Render blueprint and worker notes  
- **`docs/WEB_DASHBOARD.md`** — dashboard UI (grid, per-chart filters, alerts), relay/env vars  
- **`docs/COIN_API_CREDIT_STRATEGY.md`** — splitting load across CoinGecko / CoinMarketCap / Polygon, **rate limits & backoff**, **bulk `/coins/markets`** alias fetching  
- **`docs/API_MONTHLY_BUDGET_ESTIMATE.md`** — rough monthly HTTP estimates per provider  
- **`docs/API_PROVIDER_DEEP_ANALYSIS.md`** — which API fits which pipeline stage  
- **`docs/CROSS_PROVIDER_IDENTITY.md`** — translating ids/slugs across vendors; **`identity`** on qualified snapshot rows  

Optional **`config.json`** keys include **`COINGECKO_CALLS_PER_MINUTE`**, **`CMC_CALLS_PER_MINUTE`**, **`POLYGON_CALLS_PER_MINUTE`** (see **`config.json.example`**).

## Contributing / CI

`scripts/ci_verify.sh` is the same command Render’s **worker** runs at build time: **ruff**, **`python scripts/check_exchange_print_ascii.py`** (no non-ASCII on `print()` lines under `exchange_data/`), **mypy** on `config` + `notifications`, **`scripts/check_backtesting_imports.py`**, **`scripts/verify_backtest_env.py`**, **`compileall`**, **`pytest tests/`**, plus **`tests/test_render_rootdir_imports.py`** (imports `push_server` / `snapshot_server` `app` with Render-style `rootDir` cwd). Use **`requirements-ci.txt`** in CI and on fresh clones when mirroring the worker install.

**Production diagnostics:** if the dashboard looks empty but the worker ran, check the snapshot relay (`scripts/check_snapshot_relay.py` from a shell that has relay env vars, or open `/relay-health` on the relay host). Worker logs may show **`EXCHANGE_UNIVERSE_FALLBACK`** when exchange listings never populated—often a failed listings refresh (see `exchange_data` logs).

PRs should keep **`python scripts/check_github_ci.py`** green if you use that helper.

---

### GitHub “About” copy (paste into the repository description field)

**Short (≤350 characters):**

> Scanner for exchange-listed coins: volume/momentum filters, OHLCV uniformity, integrated backtests. Results ship to a static web dashboard (`docs/dashboard`) plus optional snapshot relay and browser push—no third-party chat delivery.

**Topics to add:** `cryptocurrency` `trading` `coinbase` `kraken` `technical-analysis` `python` `render` `github-pages`

**Website field:** your GitHub Pages URL for `docs/dashboard`, or your deployed snapshot relay root if you prefer.
