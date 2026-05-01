# Linear Trend Spotter — Execution Plan

**Purpose:** Single reference for engineering milestones (code quality, Render pipeline, Telegram links, API cost reduction, modular backtesting for a future web app, public qualified-coin dashboard + PWA + client-side UX).  
**Living document:** Checkboxes are updated as work completes.  
**Last reviewed:** 2026-04-30

---

## Table of contents

1. Non-regression & scope guardrails  
2. Instructions for the implementing agent  
3. Master execution order (phases A–Q)  
4. Technical reference (OHLCV chain + provider strategy)  
5. Milestones **A** through **Q** (tasks and verification)  
6. **Risks, follow-ups & operational checklist** (post-H4 / H6 / J2 / Q2)  
7. Progress summary & appendix  

---

## Non-regression & scope guardrails (mandatory for all milestones)

These rules apply to **every** milestone unless a task explicitly says otherwise and product approves a behavior change.

1. **Same scan universe:** Do **not** reduce the number of coins considered vs current behavior for the same `config.json` / env. In particular, do **not** lower `TOP_COINS_LIMIT`, drop exchanges from `TARGET_EXCHANGES`, or narrow the listing universe as a way to save API credits—unless a **separate, explicitly approved** product milestone exists. Internal optimizations (bulk requests, better caching, deduped calls) must preserve **≥** the same candidate set as today.
2. **Same scan interval:** Do **not** change `SCAN_INTERVAL_SECONDS` (Render), cron schedule, or worker timing as part of this plan. Cadence stays **identical** unless a dedicated ops/product change is approved outside this document.
3. **Additive by default:** New features (Milestones **J–Q**) must be **disabled or no-op** until opt-in via config/env, **or** must reproduce current outputs when the flag is off. No silent removal of notifications, backtests, or qualification stages in default configuration.
4. **No regression gate:** After each milestone, existing **verify** scripts in CI (Milestone A) and any milestone-specific verification must pass. For scan-touching work, document in Notes: same key counts as baseline (e.g. symbols loaded, final qualified count within expected variance for a fixed seed run if applicable).
5. **GitHub CI green before advancing:** Do **not** mark a milestone’s tasks complete in this file and do **not** start the **next** milestone in **Master execution order** until **`main`**’s latest run of [`.github/workflows/ci.yml`](https://github.com/edwardlthompson/linear-trend-spotter/blob/main/.github/workflows/ci.yml) has **`conclusion: success`**. Locally or before pushing milestone work, run `python scripts/check_github_ci.py` (requires authenticated **`gh`** CLI, or **`GITHUB_TOKEN`** / **`GH_TOKEN`** with Actions read access). Exit `2` means the latest run is still in progress—wait and re-run. On GitHub itself, rely on branch protection + required checks when enabled (**A4**).
6. **OHLCV chain unchanged in priority:** Per **Authoritative OHLCV policy** (Technical reference)—never swap provider order to save cost.
7. **Public dashboard (Milestone Q):** Snapshot serialization must **not** add provider HTTP calls; it only mirrors data already computed in the scan.

---

## Instructions for the implementing agent (mandatory)

Complete milestones in the order defined in **Master execution order** (default: **A → B → … → Q**), unless a task explicitly allows parallel work. **Consult the Non-regression & scope guardrails section before marking work complete.** For **every task**:

1. **Implement** the described change in code/config/docs as specified.
2. **Error-check** using the task’s **Verification** steps. If none are listed, run at minimum:
   - `python -m compileall -q .` from the repository root  
   - Any script or command named in the task  
   - If the task touches imports used on startup: `python -c "import main"` (Linux/Render path) or the narrowest import that covers the change  
3. **Do not** mark a checkbox `[x]` until verification passes.
4. **Update this file** in the same change set (or immediately after merge) by changing `- [ ]` to `- [x]` for completed tasks only. Add a short **Notes** line under the task if you discovered follow-up work (optional sub-bullet).
5. If verification fails, **fix or revert**, re-run verification, then check the box.
5a. **GitHub CI on `main`:** Before checking milestone boxes or starting the **next** milestone, confirm the latest **`CI` / `ci.yml`** run on `main` is **success** (see Non-regression guardrail **5**). Run `python scripts/check_github_ci.py` from the repo root when working locally; if it fails, fix CI first, then continue milestone work.
6. **Render:** After changes merge to the branch Render tracks (usually `main`), confirm the dashboard shows a successful deploy when applicable. Do not mark deploy-dependent tasks complete if the build failed on Render.

**Checkbox format:** Use exactly `- [ ]` (incomplete) and `- [x]` (complete) so searches and parsers stay consistent.

---

## Master execution order (phases A–Q)

Follow this order unless a task explicitly allows parallel work. **Prerequisite:** Render repo/branch confirmed (**A1**) before relying on auto-deploy for any milestone.

| Phase | Milestones | Purpose |
|-------|------------|---------|
| **1 — CI & core hardening** | **A → B → C → D → E → F** | Automated checks, exceptions, Telegram HTTP safety, pins/ruff, cross-platform dev, logging. **A2** CI should exist before broad refactors (**I2**, **M1**). After phase 1, keep **`main` CI green** before each later milestone (`python scripts/check_github_ci.py` + required checks). |
| **2 — Product-facing scanner** | **G → H** | CMC links in Telegram, then CoinGecko measurement (**H0** first) and savings / OHLCV alignment **without** shrinking universe or interval. |
| **3 — Maintainability** | **I** | DB docs / `main.py` split; can start late in phase 2 if careful, but prefer after **F**. |
| **4 — Extended ops & features** | **J → K → L → M → N → O** | Observability, Telegram extras, data/strategy, pytest/pre-commit/docker, security, research flags (all additive defaults). |
| **5 — Web surface** | **P → Q** | Backtest library boundaries, then dashboard **Q1–Q6 → Q7–Q9 → Q10–Q21**. |

**Within Milestone Q:** **Q1–Q3** (schema, writer, redaction) → **Q4–Q6** (UI shell, CORS, Pages) → **Q7–Q9** (PWA + tier-A notifications) → **Q10–Q21** (client-only dashboard UX). **Q19–Q20** may require optional fields in the snapshot JSON agreed in **Q1/Q2**; implement UI to **gracefully omit** when fields absent.

**Parallelism (allowed):** **M** with **K** once CI (**A2**) is green. **P** may overlap **early Q** (e.g. **Q1** schema) but complete **P** before a separate HTTP API repo consumes the library. **H** coordinates with **G** (URLs in payloads).

**Execution readiness (before A2):** Python 3.11 locally; Render env vars documented; no secrets in git.

---

## Technical reference

### Authoritative OHLCV policy

**CoinGecko first** → **Polygon second** → **CoinMarketCap third** for any path that fetches OHLCV or equivalent price history. Cost reduction (Milestone H) must **not** reverse this order; savings come from caching, bulk endpoints, and cadence—not from preferring Polygon ahead of CoinGecko.

### Canonical OHLCV / price-history chain (product + engineering)

| Step | Provider | Role |
|------|----------|------|
| **1 — Primary** | **CoinGecko** | First network fetch for OHLCV and related series; cache rows keyed/namespaced as today under `coingecko` where applicable. |
| **2 — Fallback** | **Polygon** | Use when CoinGecko returns nothing, insufficient bars, validation failure, or hard errors—subject to `POLYGON_API_KEY` and symbol mapping (`X:{SYMBOL}USD`). |
| **3 — Last resort** | **CoinMarketCap** | Use only after Polygon is exhausted or unavailable for that request, within whatever **free-tier** endpoints allow (often daily-oriented or limited intraday—confirm per endpoint before relying on CMC for 1h bars). |

**Implementation map (audit when changing loaders):**

| Code path | Intended chain today | Notes |
|-----------|----------------------|--------|
| `backtesting/data_loader.py` `_get_or_fetch_1h` | Cache → **CG** → cache → **Polygon** → cache → **CMC** | CMC hourly gated on `CMC_API_KEY` / plan; may return empty on restricted tiers. |
| `backtesting/data_loader.py` `_get_or_fetch_1d_coingecko` | Cache → **CG** → **Polygon** daily → **CMC** daily closes (synthetic OHLC) | CMC leg uses close-only history when OHLC unavailable. |
| `api/price_history_fallback.py` `get_30d_prices` | **Polygon** → **CMC** | Used where CG is already applied upstream in `main.py`; hourly/daily OHLCV helpers also live here (CMC tertiary). |

Any new price/OHLCV feature must follow this chain unless explicitly exempted in this file.

### Provider strategy (free tier) — reference for Milestone H

**Problem:** CoinGecko **paid/demo** plans bill **monthly credits** per successful call; heavy OHLCV + universe scans can exhaust the budget mid-cycle. **Public** CoinGecko (no key) is rate-limited and shared—usable but fragile at scale.

**Published-style limits (verify on official pricing pages before relying on numbers):**

| Provider | Typical free constraint | Strengths for this codebase | Weak spots |
|----------|-------------------------|------------------------------|------------|
| **CoinGecko** | Demo/free tier: monthly **credits** + RPM caps; public base: low RPM, no credits | **Primary OHLCV** (`api/coingecko.py`, `backtesting/data_loader.py`, uniformity in `main.py`), tickers, IDs | Many **1 call per coin** patterns add up fast |
| **Polygon** | Free tier with key; rate/throughput limits | **Second** after CG in `data_loader`; intraday aggregates | Symbol coverage; mapping; not a full “top coins” universe API alone |
| **CoinMarketCap** | Basic: ~**10k calls/month**, ~**30 RPM** (verify on [CMC pricing](https://coinmarketcap.com/api/pricing)) | Listings/quotes in bulk; **tertiary** OHLCV where endpoints allow; Telegram URLs (Milestone G) | **Historical OHLCV** on the lowest tier may be **thin vs CG**—treat as last resort, not primary |

**Conclusion for “free only” and ~50% CoinGecko reduction (without violating OHLCV order or non-regression guardrails):**

1. **Telegram links → CoinMarketCap** (Milestone G): Prefer **`/currencies/{slug}/`**. With **`TOP_COINS_PROVIDER=cmc`**, listings supply CMC slugs directly. With **`TOP_COINS_PROVIDER=coingecko`**, use **G8**: cached **`/v1/cryptocurrency/map`** + **`gecko_id_to_cmc_slug`** learn file (`CMC_SLUG_MAP_*` config) to set **`cmc_slug`** / `source_url`—bounded CMC map refresh credits, not per-notification HTTP.
2. **Operational (within guardrails):** Tune **caches** (`CACHE_PRICE_HOURS`, `CACHE_GECKO_ID_DAYS`) only where staleness remains acceptable **and** qualification outputs match baseline runs; **do not** reduce `TOP_COINS_LIMIT` or scan interval for savings (see Non-regression section).
3. **Architecture:** Prefer **bulk** CoinGecko endpoints where one call returns many coins instead of per-coin calls; ensure SQLite OHLCV cache (`database/cache.py`) is checked **before** repeating the same CG request.
4. **Do not** use “Polygon-first” or “CMC-first” for OHLCV to save credits; use **cache hits**, **bulk endpoints**, **mapper/list cadence**, and optional **`TOP_COINS_PROVIDER=cmc`** for **universe/listing** metadata only (same universe size)—keeping **CG → Polygon → CMC** for bars.
5. **Tertiary CMC:** Wire CMC OHLCV only **after** Polygon fails in loaders that still lack it (see **H4**).

Re-verify quotas on official docs before large refactors.

---

## Milestone A — Render pipeline & CI gate

**Goal:** Merges to `main` stay deployable; Render continues **auto-deploy on commit** (`render.yaml`: `autoDeployTrigger: commit`).

### Tasks

- [x] **A1.** Confirm in Render Dashboard: service linked to correct **repo** and **branch**, **Auto-Deploy** enabled.  
  - **Verification:** Screenshot or written confirmation in Notes (not committed secrets).
  - **Notes:** Verified via Render MCP (`linear-trend-spotter-worker`, `main`, auto-deploy on commit, `render.yaml` blueprint sync).
- [x] **A2.** Add `.github/workflows/ci.yml`: Python **3.11**, shared **`bash scripts/ci_verify.sh`** with Render (`requirements-ci.txt`, ruff, `verify_backtest_env`, `compileall`, import guard).  
  - **Verification:** Actuator: push branch, workflow green; locally mirror commands.
- [x] **A3.** (Optional) Add `ruff check .` with `pyproject.toml` `[tool.ruff]` once Ruff is introduced (may align with Milestone D).  
  - **Verification:** CI job passes.
- [ ] **A4.** GitHub **branch protection** on `main`: require the CI check before merge.  
  - **Verification:** Repo settings documented in Notes.
  - **Notes:** Requires org/repo admin in GitHub **Settings → Branches**; cannot be completed from this codebase alone.

---

## Milestone B — Exception handling & bare `except`

### Tasks

- [x] **B1.** `scheduler.py`: replace bare `except:` on lock unlink with `except OSError:`; log if useful.  
  - **Verification:** `python -m compileall scheduler.py`; on Linux/WSL, run scheduler lock path smoke test if available.
- [x] **B2.** `manage_bot.py`: replace bare `except:` with specific types (`ValueError`, `OSError`, `ProcessLookupError`, etc.).  
  - **Verification:** `python -m compileall manage_bot.py`.
- [x] **B3.** Review `bot_watchdog.py` for same patterns.  
  - **Verification:** `compileall` + quick manual run of entrypoint if applicable.

---

## Milestone C — Telegram HTTP & HTML safety

### Tasks

- [x] **C1.** `telegram_bot.py` `get_updates`: check HTTP status / `response.ok` before `json()`; handle `JSONDecodeError`.  
  - **Verification:** `compileall`; optional `scripts/verify_telegram.py` with test creds.
- [x] **C2.** `notifications/telegram.py`: harden `_request` / `send_photo` similarly.  
  - **Verification:** `compileall`.
- [x] **C3.** Escape user/API-derived strings for Telegram **HTML** (`html.escape` or equivalent) in `MessageFormatter` and any raw HTML assembly in `main.py` / `telegram.py`.  
  - **Verification:** Unit test or small script with `<`, `>`, `&` in symbol/name; message still valid.

---

## Milestone D — Dependencies & tooling

### Tasks

- [x] **D1.** Add `pyproject.toml` with `[tool.ruff]` (target Py 3.11, sensible excludes for `scripts/` if needed).  
  - **Verification:** `ruff check .` passes in CI/local.
- [x] **D2.** Pin `requirements.txt` (via `pip freeze` from clean 3.11 env or `pip-tools`).  
  - **Verification:** Fresh venv `pip install -r requirements.txt` succeeds; CI passes.
- [ ] **D3.** (Optional) `mypy` incremental on `config/` + `notifications/`.  
  - **Verification:** `mypy` passes on scoped paths.

---

## Milestone E — Cross-platform dev ergonomics

### Tasks

- [x] **E1.** `scheduler.py`: replace or guard `fcntl` (e.g. `portalocker` fallback on Windows) so import works on Windows dev machines.  
  - **Verification:** `python -c "import scheduler"` on Windows **and** Linux/WSL or CI.
- [x] **E2.** `manage_bot.py`: replace `tail` with Python tail; use `sys.executable` instead of `python3` for subprocess.  
  - **Verification:** Run `status` / `start` / `stop` smoke on target OS (or document Linux-only).
- [x] **E3.** `bot_watchdog.py`: `sys.executable` instead of `python3`.  
  - **Verification:** `compileall`.

---

## Milestone F — Logging vs `print`

### Tasks

- [x] **F1.** Migrate runtime modules (`config/settings.py`, `database/cache.py`, `utils/metrics.py`, `utils/rate_limiter.py`, etc.) to `logging` with consistent logger names.  
  - **Verification:** Run one full scan dry-run or worker start; logs appear without losing warnings.
- [x] **F2.** Document convention: CLI `scripts/*.py` may keep `print` or use dedicated loggers.  
  - **Verification:** README or short comment in `utils/logger.py` Notes.

---

## Milestone G — Telegram: CoinMarketCap links (not CoinGecko)

**Goal:** User-facing links in Telegram notifications and keyboards prefer **CoinMarketCap** coin pages.

### Tasks

- [x] **G1.** Add `MessageFormatter._build_cmc_url(coin: dict) -> str` (slug → `https://coinmarketcap.com/currencies/{slug}/`; optional fallback by symbol search URL if product accepts).  
  - **Verification:** Manual test with dict containing `slug` only / `slug`+`gecko_id` / neither.
- [x] **G2.** `format_entry`: ensure header `<a href>` uses **CMC URL** when `slug` or `cmc_url` exists; do not prefer `_build_coingecko_url` for display. Align with `source_url` policy in `main.py` if needed.  
  - **Verification:** Generated HTML caption shows `coinmarketcap.com` link.
- [x] **G3.** `format_exit`: replace `gecko_url` / `_build_coingecko_url` with CMC-first link line.  
  - **Verification:** Exit message contains CMC URL when slug present.
- [x] **G4.** `notifications/telegram.py` (`_build_context_keyboard`, `send_exit_alert`): use CMC URL builder instead of `_build_coingecko_url` for “Analyze Coin” / source links.  
  - **Verification:** Keyboard URL opens CMC in browser.
- [x] **G5.** `database/models.py` `_build_source_url`: reorder or adjust so **CMC slug URL** is preferred over CoinGecko when `slug` is available (consistent DB-derived links with Telegram).  
  - **Verification:** History insert path produces `cmc_url`/stored URL matching policy; no regression on coins without slug.
- [x] **G6.** `main.py` / `api/coingecko.py` `source_url` assignments: when slug exists from CMC path, set **`https://coinmarketcap.com/currencies/{slug}/`** instead of CoinGecko coin page for notification-facing `source_url`.  
  - **Verification:** End-to-end scan with `TOP_COINS_PROVIDER=cmc` produces CMC `source_url` on sample coin.
- [x] **G7.** Update `linear-trend-spotter-spec.md` or README notification section if spec still mandates CoinGecko links.  
  - **Verification:** Doc grep shows CMC as primary user link.
- [x] **G8.** When `TOP_COINS_PROVIDER=coingecko`, resolve **real CoinMarketCap currency slugs** for Telegram (avoid `coinmarketcap.com/search/?q=` when a confident match exists): cache **CMC `/v1/cryptocurrency/map`** under `DATA_DIR` (`CMC_SLUG_MAP_*` keys), index by **symbol** with **name** disambiguation, persist **`gecko_id → cmc_slug`** learn file across scans; set `cmc_slug` / `cmc_url` / `source_url` on qualified coins.  
  - **Verification:** With `CMC_API_KEY` + map cache populated, a CG-top run yields `/currencies/{slug}/` links for common symbols; ambiguous symbols still fall back to search.  
  - **Notes:** `utils/cmc_slug_resolver.py`, `CoinMarketCapClient.fetch_cryptocurrency_map_page`, `MessageFormatter` / `_build_source_url` honor **`cmc_slug`**. Refresh is credit-bounded (paginated `limit=5000`); tune **`CMC_SLUG_MAP_MAX_AGE_HOURS`** (default 72). Disable with **`CMC_SLUG_MAP_ENABLED`: false**.

---

## Milestone H — Reduce CoinGecko usage (~50%) on free tier

**Goal:** Measurable drop in CoinGecko successful calls per scan cycle without breaking qualification/backtests.

### Tasks

- [x] **H0. Measurement (do first)**  
  - Add lightweight **counters or structured logs** (per scan): CoinGecko requests by endpoint family (markets, OHLCV, mapper, tickers). Log to existing metrics file or `app_logger` summary line at scan end.  
  - **Verification:** One scan produces a numeric summary; baseline saved in Notes.
  - **Notes:** Implemented via `utils/coingecko_usage.py` (`record_coingecko_http`) from `api/coingecko.py` (`_make_request` + `/coins/markets` pages) and `api/coingecko_mapper.py` (`/coins/list`). Counters live in `metrics.counts` as `coingecko_http_*`, appear in `metrics.report()` / persisted `metrics.json` history. Save your first post-deploy **totals** here as baseline when tuning **H1–H6**: _e.g. `coingecko_http_total`, `markets`, `market_chart`, `coin_detail`, `tickers`, `ohlc`, `coins_list`._ **Follow-up:** paste **before** and **after** counter blocks (same `config.json`, same cadence) under this Note or in **Section 6.1** to close the **H6 ≥50%** evidence gap.

- [x] **H1. Cache & config tuning (low risk, no universe/interval change)**  
  - Tune `CACHE_PRICE_HOURS` / `CACHE_GECKO_ID_DAYS` only with **before/after qualification comparison** on a fixed config (same `TOP_COINS_LIMIT`, same exchanges, same `SCAN_INTERVAL_SECONDS`); ensure `BACKTEST_RESUME_ENABLED` avoids duplicate heavy fetches. **Do not** reduce coin universe or interval.  
  - **Verification:** H0 metrics improve; qualified-coin counts / alert cardinality within agreed tolerance vs baseline (document in Notes).
  - **Notes:** Default **`CACHE_PRICE_HOURS` 6 → 12** so hourly workers reuse SQLite OHLCV / price rows across consecutive scans (fewer CoinGecko `market_chart` / related hits for the same symbol within 12h). **`CACHE_GECKO_ID_DAYS`** is now enforced: `/coins/list` runs when mappings are **empty** or metadata **`last_update`** is older than this setting (default 30d)—replacing “only refresh when empty” so new listings age in on schedule without per-scan list pulls. `BACKTEST_RESUME_ENABLED` unchanged (still avoids duplicate heavy backtest work). **Post-merge:** capture one **H0** counter block before/after on the same `config.json` and paste baseline deltas here if product wants a signed-off %.

- [x] **H2. Bulk vs per-coin**  
  - Audit `api/coingecko.py` and `main.py` for redundant per-coin calls; consolidate to list/markets endpoints where possible.  
  - **Verification:** H0 metrics show fewer calls for same universe size.
  - **Notes:** **(1)** `COINGECKO_ID_ALIASES` now prefetches via batched `/coins/markets?ids=…` (chunked) instead of one `/coins/{id}` per aliased symbol; misses still fall back to `get_coin_market_snapshot`. **(2)** STEP 6 dedupes `/coins/{id}/tickers` by `cg_id` (one HTTP call per distinct id among uncached coins). **(3)** Tickers requests pass `exchange_ids` (config `TARGET_EXCHANGES` mapped to CG identifiers, e.g. `mexc`→`mxc`) for smaller payloads. **(4)** When `TOP_COINS_PROVIDER=coingecko`, STEP 5 uses `slug` from the markets row as CoinGecko id (avoids redundant mapper lookups; same id as `/coins/markets` universe).

- [x] **H3. Provider mix (universe vs OHLCV)**  
  - Document and test Render env: e.g. `TOP_COINS_PROVIDER=cmc` for **top-coin / listing** pulls while **OHLCV remains CG → Polygon → CMC** per canonical chain.  
  - **Verification:** Full scan completes; backtest stage still meets minimum pass rate defined in runbook.
  - **Notes:** README and CI/deployment docs cover Render `config.json` + `TOP_COINS_PROVIDER=cmc` with unchanged OHLCV order. CI/backtest smoke unchanged (no live scan in CI).

- [x] **H4. Align all OHLCV paths with CG → Polygon → CMC**  
  - Audit `main.py` (uniformity / 30d paths), `backtesting/data_loader.py`, and `api/price_history_fallback.py`; document each call site in the Appendix table.  
  - Implement **CMC as explicit third step** where missing (e.g. hourly/daily after Polygon fails), gated on `CMC_API_KEY` and endpoint capability; do **not** reorder ahead of CoinGecko.  
  - **Verification:** `scripts/verify_backtest_data.py` (or agreed subset) passes; logs show fallback order when CG is stubbed or forced to fail in a dev test.
  - **Notes:** `PriceHistoryFallbackClient.get_cmc_hourly_ohlcv` + `get_polygon_30d_daily_ohlcv`; `BacktestDataLoader` and `main.py` STEP 7 cache under `cmc`; Appendix technical table updated. **Risk / follow-up:** CMC **hourly OHLCV** and historical depth depend on your [CMC API plan](https://coinmarketcap.com/api/pricing); on the lowest tiers the endpoint may return **403/empty**—the chain then correctly stays on CoinGecko/Polygon. Monitor worker logs for `cmc_api` / missing tertiary; upgrade CMC or rely on CG+Polygon if hourly CMC never populates. Details: **Section 6.2**.

- [x] **H5. Mapper refresh cadence**  
  - `CoinGeckoMapper.fetch_coingecko_list`: ensure full list refresh is not triggered too often (configurable interval or “stale after N days”).  
  - **Verification:** Logs show list fetch frequency matches new policy.
  - **Notes:** Delivered under **H1** (`should_refresh_list` + `CACHE_GECKO_ID_DAYS`); no additional code change in this milestone pass.

- [x] **H6. Final**  
  - Confirm **≥50%** reduction vs H0 baseline **or** document why not achievable on free tier (then narrow scope: e.g. paid CG tier or acceptable product limits).  
  - **Verification:** Before/after numbers in Notes; stakeholder summary in this file (short paragraph under H).
  - **Notes:** **H0–H4** reduce redundant calls (counters, cache TTL, batched markets, deduped tickers, CMC tertiary). A signed-off **≥50%** figure still needs two production counter dumps on identical config (paste under H0 Notes or **Section 6.1**). On strict free tiers, hourly CMC OHLCV may be unavailable—Polygon/CG remain primary; document plan tier against [CMC pricing](https://coinmarketcap.com/api/pricing). **Checklist:** Sections **6.1–6.2**.

### Stakeholder summary (H6)

Engineering closed the **canonical OHLCV chain** (CoinGecko → Polygon → CoinMarketCap) in the scanner and backtest loader without shrinking universe or scan cadence. **CoinGecko credit savings** come from earlier milestones (**H0–H2**) plus optional CMC offload for **listings** (`TOP_COINS_PROVIDER=cmc`). A finance-ready **“≥50% fewer CG calls”** proof still needs two timed counter exports on the same `config.json`; until then, treat **H6** as *architecturally complete / measurement pending*. **Operational detail:** see **Section 6 — Risks, follow-ups & operational checklist** below.

---

## Milestone I — Database clarity & `main.py` modularization (lower priority)

### Tasks

- [x] **I1.** Document `Database.execute` transaction semantics; consider `PRAGMA journal_mode=WAL` where missing for write-heavy DBs.  
  - **Verification:** Doc + optional stress note only.
  - **Notes:** `database/models.py`: class/method docstrings for `execute()` autocommit semantics; `get_connection()` enables **WAL** on `Database` subclasses (`PriceCache` already used WAL).
- [ ] **I2.** Split `main.py` into modules (pipeline stages) in incremental PRs.  
  - **Verification:** CI + import smoke tests pass; behavior unchanged with default config (non-regression).
  - **Notes:** First extraction: CMC symbol resolution helpers live in `scanner/cmc_resolve.py` (`build_cmc_normalized_lookup`, `resolve_cmc_data`); `main.py` imports them. **2026-04-30:** Tier-B worker notify hook moved to `scanner/web_push_notify.py` (`maybe_notify_web_push_scan`). **2026-05-01:** Event-summary active ranking rows extracted to `scanner/active_ranking.py` (`build_active_ranking_rows`); weekly digest helpers extracted to `scanner/weekly_digest.py` (`load/save state`, `iso_week_key`, `build_weekly_digest_message`); anomaly detector message builder extracted to `scanner/anomaly_alerts.py` (`build_anomaly_messages`); top-coin resolution + CMC notify URL helpers extracted to `scanner/top_coin_resolution.py` (`resolve_top_coin_data`, `ensure_cmc_notify_urls`); rank/signal/volume enrichment extracted to `scanner/coin_enrichment.py` (`attach_rank_movement`, `attach_signal_age`, `attach_volume_acceleration`); ticker/daily-bar processing extracted to `scanner/market_processing.py` (`process_tickers`, `aggregate_daily_bars_from_hourly`); quiet-window toggle helper extracted to `scanner/quiet_hours.py` (`telegram_quiet_active`); initialization/bootstrap block extracted to `scanner/runtime_init.py` (`initialize_runtime_components`). Further stage splits still pending.

---

## Milestone J — Observability & operations

*Promoted from former backlog (“Observability & operations”). Must satisfy **Non-regression** defaults.*

### Tasks

- [x] **J1.** **Structured JSON logging** (optional dual output): one JSON line per major event alongside existing human-readable logs; off by default or env-gated.  
  - **Verification:** With feature off, log output matches prior shape; with on, valid JSON lines; `compileall`.
  - **Notes:** Set env `STRUCTURED_JSON_LOGGING=1` (or `true`/`yes`/`on`). `maybe_install_structured_json_handler()` runs at start of `run_scanner()`; adds JSON-lines `StreamHandler` on logger `trend_scanner` (stderr) in addition to existing formatters.

- [x] **J2.** **Heartbeat / health artifact:** write a small JSON file to `DATA_DIR` (or fixed path) after each successful scan (timestamp, duration, status)—no change to scan logic.  
  - **Verification:** File appears after run; interval and universe unchanged.
  - **Notes:** `SCAN_HEARTBEAT_ENABLED` (default **false**); `utils/scan_artifacts.write_scan_heartbeat`; filename `SCAN_HEARTBEAT_FILE` (default `scan_heartbeat.json`). **Ops:** enable only when you want a Render-readable health file; see **Section 6.3** (retention, disk).

- [x] **J3.** **Scan cost dashboard:** extend `scanner_insights.json` or add `scan_costs.json` with CG/Polygon/CMC call counts and cache hit rates (can build on H0 counters).  
  - **Verification:** Artifact valid JSON; scan completes; counts non-decreasing for same work (no dropped coins).
  - **Notes:** `SCAN_COSTS_ENABLED` / `SCAN_COSTS_FILE` (default **false** / `scan_costs.json`). `utils/scan_costs.write_scan_costs_file` after `metrics.save`. Polygon/CMC HTTP tallies via `utils/provider_http_usage.py` from `api/price_history_fallback.py` and `api/coinmarketcap.py` (H0 CoinGecko counters unchanged).

- [x] **J4.** **Graceful degradation (opt-in only):** env flag e.g. `DEGRADE_SKIP_BACKTEST_ON_CG_CREDITS=0` default; when enabled and credits below threshold, skip backtest with explicit Telegram notice. **Default must preserve full pipeline.**  
  - **Verification:** Default off → identical stages vs baseline; on → documented behavior only.
  - **Notes:** `DEGRADE_SKIP_BACKTEST_ENABLED` + `DEGRADE_PRIOR_CG_HTTP_SKIP_GE` in `config.json`. If enabled and `SKIP_GE` **≤ 0**, every run skips backtests (emergency). If `SKIP_GE` **> 0**, skip when **prior** `metrics.json` last entry `coingecko_http_total` ≥ threshold; else run backtests. Telegram HTML notice when skipped (if bot enabled).

---

## Milestone K — Telegram & UX enhancements

*Promoted from former backlog (“Telegram & UX”). All bot additions must be **additive**; default polling/commands unchanged when disabled.*

### Tasks

- [x] **K1.** **`/health`**, **`/last`**, **`/cost`** (or similar) read-only commands in `telegram_bot.py` reading persisted metrics/heartbeat; feature flag default **off** or commands no-op until enabled.  
  - **Verification:** Flag off: no behavior change for existing flows; flag on: commands return expected text.
  - **Notes:** **`SCANNER_DIAG_COMMANDS_ENABLED`** (default **false**). **`/health`**: `SCAN_HEARTBEAT_FILE` + last `metrics.json` **`coins_processed`**. **`/last`**: last metrics row timestamp/duration. **`/cost`**: **`coingecko_http_*`** slice + Polygon/CMC totals + note if **`scan_costs.json`** exists. Commands parsed with **`/cmd@BotName`** stripping.

- [x] **K2.** **Quiet hours:** config window (UTC) suppressing non-critical alerts; **entries/critical unchanged** when disabled; default = no quiet hours.  
  - **Verification:** Default config sends same alerts as today; quiet window suppresses only configured classes.
  - **Notes:** **`QUIET_HOURS_ENABLED`** (default **false**). **`QUIET_HOURS_START_HOUR_UTC`** / **`QUIET_HOURS_END_HOUR_UTC`** (default **22**→**6**, wrap). Per-class toggles: **`QUIET_HOURS_SUPPRESS_ANOMALY`**, **`QUIET_HOURS_SUPPRESS_WEEKLY_DIGEST`**, **`QUIET_HOURS_SUPPRESS_EVENT_SUMMARY`**, **`QUIET_HOURS_SUPPRESS_STILL_QUALIFYING`** (defaults **true** when quiet). Entry/exit/degrade Telegram paths are **not** gated.

- [x] **K3.** **Per-exchange deep links** in formatter/keyboard (Coinbase/Kraken/MEXC) **in addition to** CMC link; no removal of existing buttons.  
  - **Verification:** Manual Telegram check; links resolve.
  - **Notes:** **`MessageFormatter.exchange_url_buttons`** + **`TelegramClient.coin_link_reply_markup`**; entry/exit **`send_photo`/`send_message`** in **`main.py`** use that markup (Chart / Analyze + per-exchange URL rows).

- [x] **K4.** **Message edit** path for “still qualifying” (optional): use `editMessageText` only when config enabled; default off.  
  - **Verification:** Default off: message volume unchanged vs baseline.
  - **Notes:** **`STILL_QUALIFYING_EDIT_ENABLED`** (default **false**) + **`NO_CHANGE_NOTIFICATIONS`**. One roster message per chat; **`STILL_QUALIFYING_STATE_FILE`** stores **`message_id`** under **`DATA_DIR`**; cleared on any entry/exit. **`utils/still_qualifying_notify.py`**.

---

## Milestone L — Data & strategy extensions

*Promoted from former backlog (“Data & strategy”). Defaults must match current min bars and notification content.*

### Tasks

- [x] **L0.** **Gain filter thresholds (FILTER 1 + exit parity):** configurable **`GAIN_FILTER_MIN_7D_PERCENT`** (default **7**, inclusive) and **`GAIN_FILTER_MIN_30D_PERCENT`** (default **30**, exclusive upper bound so **30d must be > 30** as before); keep **30d > 7d** momentum rule. Applied in **`main.py`** STEP 3 and exit-reason re-checks.  
  - **Verification:** Default config tightens 7d vs legacy (was no 7d floor); set **`GAIN_FILTER_MIN_7D_PERCENT`: 0** to approximate prior behavior on 7d only.  
  - **Notes:** Product intentionally **drops** coins whose **7d gain is below the minimum**; narrows qualified set vs pre-change (not a universe/API shrink—filter logic only).

- [x] **L1.** **Configurable OHLCV min bars** per timeframe in `config.json` with validation in `settings.py`; **defaults equal current hardcoded behavior.**  
  - **Verification:** Default config → same skip/pass rates as before on `verify_backtest_*` sample.
  - **Notes:** **`OHLCV_MIN_1H_BARS_PER_DAY`** (24), **`OHLCV_MIN_1H_BARS_SLACK`** (12), **`OHLCV_MIN_1H_BARS_FLOOR`** (600) → `max(per_day·days−slack, floor)` hourly threshold; **`OHLCV_MIN_1D_BARS_SLACK`** (2), **`OHLCV_MIN_1D_BARS_FLOOR`** (25) → daily. Wired in **`backtesting/data_loader.py`** (`BacktestDataLoader`).

- [x] **L2.** **Symbol quality score** line in notifications (data age, provider mix); additive field; can be hidden via config defaulting to current look.  
  - **Verification:** Default hides or matches “no extra line” per product choice; no dropped alerts.
  - **Notes:** **`NOTIFICATION_SYMBOL_QUALITY_LINE`** (default **false**). **`MessageFormatter._symbol_quality_line_html`** appends reliability / **`ohlcv_source`** / **`signal_age_label`** to entry and exit captions when enabled.

- [x] **L3.** **Watchlist export** (CSV/JSON) on schedule or command; writes to `DATA_DIR`; no change to core scan.  
  - **Verification:** Export file valid; scan unaffected.
  - **Notes:** **`WATCHLIST_EXPORT_ENABLED`** (default **false**); **`WATCHLIST_EXPORT_CSV_FILE`** / **`WATCHLIST_EXPORT_JSON_FILE`**. Near-miss rows from **`compute_watchlist_rows`** (uniformity buffer band + non-positive 30d return with passing score). **`scripts/export_watchlist.py`** prints path/row count.

- [ ] **L4.** **Backtest A/B shadow:** second profile on subset, logs only, **no Telegram** unless opt-in; default off.  
  - **Verification:** Off → no extra runtime; on → logs only, same primary alerts.

---

## Milestone M — Engineering quality

*Promoted from former backlog (“Engineering quality”).*

### Tasks

- [x] **M1.** **`pytest`** suite: migrate or wrap `scripts/verify_*.py` assertions into tests; golden-file tests for `MessageFormatter` HTML output.  
  - **Verification:** `pytest` green in CI; existing verify scripts still runnable.
  - **Notes:** `tests/test_formatter_cmc_urls.py` (CMC `/currencies/` vs search + `format_entry` header), `tests/test_public_snapshot.py`; `scripts/ci_verify.sh` runs `pytest tests/`; further golden HTML files optional.

- [x] **M2.** **Pre-commit:** `.pre-commit-config.yaml` with `ruff` + `compileall` (or `ruff` only if compileall covered by CI).  
  - **Verification:** `pre-commit run --all-files` passes.
  - **Notes:** `.pre-commit-config.yaml` uses `ruff-pre-commit` only (`compileall` remains in CI / `scripts/ci_verify.sh`).

- [x] **M3.** **`docker compose`** (optional) local profile with `PYTHON_VERSION`, `DATA_DIR`, and Render env keys as optional blanks.  
  - **Verification:** `docker compose config` valid; README one-liner.
  - **Notes:** Root **`docker-compose.yml`** — `app` service runs **`ruff`**, **`check_backtesting_imports`**, **`verify_backtest_env`**, **`compileall`** via **`requirements-ci.txt`** (parity smoke, not production worker).

---

## Milestone N — Security & compliance

*Promoted from former backlog (“Security & compliance”).*

### Tasks

- [x] **N1.** **Secret scanning:** enable GitHub push protection; add `gitleaks` (or `trufflehog`) job in CI on PR.  
  - **Verification:** CI job passes on clean repo; documented false positives.
  - **Notes:** `.github/workflows/ci.yml` job **`gitleaks`** (`gitleaks/gitleaks-action@v2`, `fetch-depth: 0`). **Push protection** for secrets is still **repo/org admin** in GitHub **Settings → Code security** (not automatable from this repo).

- [ ] **N2.** **Telegram webhook mode (optional):** config to use webhook instead of long polling; **default remains long polling** (Render-compatible).  
  - **Verification:** Default: existing worker behavior; webhook path documented separately if not used on Render.

---

## Milestone O — Product & research (optional, larger scope)

*Promoted from former backlog (“Product / research”). Each sub-feature **default off** until config enables.*

### Tasks

- [ ] **O1.** **Multi-portfolio simulation** in insights layer (additional metrics file); default off.  
  - **Verification:** Off → no extra IO; on → file written; scan interval/universe unchanged.

- [ ] **O2.** **Regime filter** (e.g. BTC dominance / vol) as **optional** qualification gate; `config` default **false**.  
  - **Verification:** Default false → bit-for-bit same qualification as baseline on sample run.

- [ ] **O3.** **Alert backtesting** report: hypothetical PnL for top-N alerted coins; offline or scheduled; **no change** to live alerts unless opt-in.  
  - **Verification:** Live Telegram unchanged with default settings.

---

## Milestone P — Backtesting modularization (reuse in web / second repo)

**Goal:** Make `backtesting/` (and tightly related data loading) a **clear, import-safe library surface** so a future **public web app** can depend on it via git submodule, `pip install git+…`, or a shared package—**without** pulling `main.py`, Telegram, or notification image code into backtest-only workflows.

### Design rules

- **Allowed imports (library tier):** `pandas`/`numpy`/`vectorbt` as today; prefer **`BacktestLoaderParams` / `BacktestRunnerParams`** from the host instead of `config.settings` (optional `*_from_settings()` helpers for the integrated worker).
- **Forbidden in library tier:** `notifications/*`, `telegram_bot.py`, `main.run_scanner` circular paths. Add a CI guard (import smoke or `ruff`/custom script) that fails if violated.
- **Outputs:** Typed or documented dicts / dataclasses consumable by HTTP layer later; optional thin `to_public_dict()` for API stability.

### Tasks

- [x] **P1.** Document **`backtesting` public API** in `docs/BACKTESTING_LIBRARY.md`: entry points (`BacktestDataLoader`, `run_backtests_for_final_results`, `BacktestConfig`, `notification_rows_for_symbol`, engine/optimizer boundaries).  
  - **Verification:** Doc reviewed; list matches actual exports used by `main.py` today.

- [x] **P2.** **Decouple settings:** replace or wrap direct `settings` singleton usage inside `backtesting/` where practical with **constructor-injected** limits (timeouts, workers, fee bps) so a web worker can construct loaders without full scanner config.  
  - **Verification:** `tests/test_backtesting_params.py` (params import + subprocess smoke; injected OHLCV gates with `pytest.importorskip("pandas")`); scanner call sites unchanged when `params` / `loader_params` omitted; `python -m ruff check .` + `scripts/check_backtesting_imports.py`.
  - **Notes:** `backtesting/params.py` — `BacktestLoaderParams`, `BacktestRunnerParams`, `loader_params_from_settings`, `runner_params_from_settings`; `BacktestDataLoader(..., loader_params=…)`; `run_backtests_for_final_results(..., params=…)`; lazy `backtesting/__getattr__` so `import backtesting` avoids pulling `pandas` until heavy symbols are used.

- [x] **P3.** **CI import guard:** script or test that imports `backtesting` package subtree and asserts no transitive import of `notifications`, `telegram_bot`, `main`.  
  - **Verification:** CI job fails if a forbidden import is introduced.
  - **Notes:** `scripts/check_backtesting_imports.py` (AST scan); invoked from `scripts/ci_verify.sh`.

- [x] **P4.** **Packaging stub (optional):** `pyproject.toml` `[project]` optional package name `linear-trend-backtest` pointing at `backtesting/` **or** documented `PYTHONPATH` layout for sibling repo.  
  - **Verification:** Second venv can `pip install -e .` (if packaged) or follow README “consume from sibling repo” without scanner.
  - **Notes:** `pyproject.toml` now has `[project]` + `[build-system]` (setuptools) + `[tool.setuptools.packages.find]` excluding `scripts/`, `docs/`, venvs. **`pip install -e .`** installs discoverable packages (`api`, `backtesting`, `scanner`, …); validate in a **Python 3.11** venv per CI (3.14+ may differ for numpy wheels).

---

## Milestone Q — Public qualified-coin dashboard (hourly; **zero extra provider API load**)

**Goal:** A **mobile-friendly** static page (e.g. **GitHub Pages** or any static host) shows coins that **reached the same stage as notification-ready** results, with **field parity** to Telegram notifications. Rows **disappear** when the next hourly snapshot omits them (no separate “delete” API). Includes an **installable PWA**, **tier-A browser notifications** (**Q7–Q9**), and **client-side UX** (**Q10–Q21**)—all without extra market API calls from browsers.

### Architecture — least taxing on CoinGecko / CMC / Polygon

| Bad pattern | Good pattern (this milestone) |
|-------------|----------------------------------|
| Browser or Pages site polls **market APIs** every visit | Site **only** `fetch()`es a **pre-built JSON snapshot** produced by the **existing scan** |
| Extra “dashboard sync” job that re-queries providers | **Write snapshot once** at end of a scan using **data already in memory** (same objects passed to `MessageFormatter` / image path)—**no additional provider HTTP calls** beyond what that scan already made |
| Refreshing more often than scans | Snapshot version bumps **only when `main`/worker completes a scan** (aligned with `SCAN_INTERVAL_SECONDS`, e.g. hourly)—static `Cache-Control` / ETag reduces bandwidth, not API usage |

**Recommended hosting split:**

1. **Worker (this repo, Render):** After successful scan, serialize **notification-parity payload** to e.g. `DATA_DIR/qualified_public_snapshot.json` + optional `qualified_public_snapshot.version.txt` (ISO timestamp). Feature flag **default off** until public launch.  
2. **Read path:** Expose file via **single GET** on Render (static file service, or minimal **read-only** HTTP route on same service) with **`Cache-Control: public, max-age=`** roughly the scan interval (or slightly less) so repeat page loads do not hammer your origin. **ETag** optional.  
3. **GitHub Pages:** Static `index.html` + JS that **fetches** the JSON URL from step 2. Configure **CORS** on the Render GET to allow your `*.github.io` origin (or proxy via same-site if you later colocate). **Browsers never hold API keys** for market data.

**Alternative (no CORS, more git noise):** Scheduled **GitHub Actions** copies committed JSON into `docs/` hourly—still **zero** market API calls from visitors, but uses **GitHub API / git writes** each run; prefer worker-hosted JSON for simplicity.

### Non-regression

- Snapshot writer **must not** trigger a second scan or refetch tickers/OHLCV; only serialize after existing pipeline steps.  
- Default flag **off** preserves current disk I/O behavior.

### Tasks

- [x] **Q1.** **JSON schema** (`docs/qualified_public_snapshot.schema.json` or markdown table): fields matching notification captions (symbol, name, gains, uniformity, health, rank fields, exchange volumes, provider volume, top backtest rows summary, `source_url`, timestamps, `schema_version`).  
  - **Verification:** Sample file hand-reviewed against one real Telegram payload.

- [x] **Q2.** **Snapshot writer** in scanner completion path: build list from the **same** structure used for alerts; write atomically (`tmp` then rename); env e.g. `PUBLIC_QUALIFIED_SNAPSHOT=1`.  
  - **Verification:** With flag on, one scan produces valid JSON; with flag off, no file or no write; **provider call counts** (H0) unchanged vs baseline for same config.
  - **Notes:** `PUBLIC_QUALIFIED_SNAPSHOT_ENABLED` / `PUBLIC_QUALIFIED_SNAPSHOT_FILE` / `PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET` in `config.json`; `utils/scan_artifacts.write_public_qualified_snapshot` after metrics save. **Q3** `field_set` **`minimal`** omits per-exchange volumes and `ohlcv_source`. **Ops / risk:** see **Sections 6.3–6.4**.

- [x] **Q3.** **Redaction / safety:** env or config for fields to omit on public JSON (e.g. internal debug); default keeps parity with notifications for allowed fields only.  
  - **Verification:** Redacted mode produces smaller JSON; no secrets in file.
  - **Notes:** `PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET`: **`full`** (default) includes `exchange_volumes`, `volume_24h`, `ohlcv_source`; **`minimal`** omits those for a smaller public file. Top-level `field_set` key in JSON; schema updated.

- [x] **Q4.** **Static dashboard:** responsive CSS, table or cards, reads JSON URL from `?api=` or baked `config.js` generated at deploy; empty state when `coins: []`.  
  - **Verification:** Manual load on narrow viewport; refresh shows updated list after next scan file update.
  - **Notes:** `docs/dashboard/` (`index.html`, `styles.css`, `app.js`, `config.example.js`). Load button + `?api=` URL encoding.

- [x] **Q5.** **CORS + caching headers** on the GET that serves the snapshot (document in `docs/WEB_DASHBOARD.md`); document **hourly** expectation tied to `SCAN_INTERVAL_SECONDS`, not per-page cron.  
  - **Verification:** Cross-origin fetch from local static server succeeds; `max-age` present.
  - **Notes:** `docs/WEB_DASHBOARD.md` — CORS, `Cache-Control`, hourly alignment. Origin must allow cross-origin fetch to snapshot URL.

- [x] **Q6.** **GitHub Pages wiring:** `docs/dashboard/` or `gh-pages` branch build instructions; **no secrets** in repo; JSON URL supplied via GitHub Actions env at build time **or** runtime fetch to public Render URL.  
  - **Verification:** Pages deploy succeeds; site loads without 4xx on JSON (use placeholder URL in CI if needed).
  - **Notes:** Same doc: copy `config.example.js` → `config.js`, set `window.__SNAPSHOT_URL__`, optional second `<script>` before `app.js` per comment in `index.html`.

### PWA & browser notifications — design (tier A vs B)

| Tier | User experience | Extra backend? | Market APIs? |
|------|-----------------|---------------|--------------|
| **A (Q7–Q9)** | Installable app icon; optional **tab-open / PWA** notifications when snapshot **version** changes (poll JSON every 15–60 min + `visibilitychange`). | **None** | **None** (only your snapshot URL). |
| **B (Q21)** | Notifications when the browser has been closed for days. | **Yes** — Web Push relay (VAPID + subscription store) invoked after each scan. | **None** for market data. |

Implement **tier A** in **Q7–Q9** first; implement **tier B** in **Q21** (document VAPID, subscription storage, and ops in `docs/WEB_DASHBOARD.md`).

### Tasks — PWA & tier-A notifications

- [x] **Q7.** **PWA shell:** add `manifest.webmanifest` (`name`, `short_name`, `start_url`, `display: standalone` or `minimal-ui`, `theme_color`, `background_color`); **maskable** and **192/512** icons; `<link rel="manifest">` + `theme-color` meta + **Apple** `apple-touch-icon` / `mobile-web-app-capable` where applicable.  
  - **Verification:** Lighthouse “PWA” or Chrome **Install app** succeeds on mobile + desktop; offline shell loads branded splash (even if data still requires network).
  - **Notes:** `docs/dashboard/manifest.webmanifest`, `docs/dashboard/icons/icon-{192,512}.png` (generated via `scripts/gen_dashboard_pwa_icons.py`), head tags in `index.html`.

- [x] **Q8.** **Service worker:** register from dashboard JS; **cache-first** for static assets (HTML/CSS/JS/icons); **network-only** (or short `networkTimeoutSeconds`) for the **snapshot JSON** so users never see stale qualified list from SW cache; bump **cache version** on deploy.  
  - **Verification:** Airplane-mode: UI shell loads; snapshot fetch fails gracefully with message; no market API calls; redeploy invalidates old asset cache.
  - **Notes:** `docs/dashboard/sw.js` — bump `CACHE_VERSION` when editing cached static files. Same-origin `*.json` requests bypass cache; cross-origin snapshot URLs are not intercepted by this SW.

- [x] **Q9.** **Tier-A notifications:** explicit **“Enable update alerts”** button → `Notification.requestPermission()`; if `granted`, start **polling** snapshot URL on an interval **≥ 15 min** (configurable constant, aligned with hourly scan); compare `updated_at` / `schema_version` / hash to previous fetch → `registration.showNotification` (preferred from SW) or `new Notification` when changed; **silent** if permission `denied` or `default`; document **iOS Safari** limitations (user gesture, PWA to home screen).  
  - **Verification:** Grant + deny paths on Chrome Android + desktop; snapshot-only network traffic; `docs/WEB_DASHBOARD.md` references **Q21** for tier-B Web Push.
  - **Notes:** `POLL_INTERVAL_MS = 15 * 60 * 1000` in `app.js`; SHA-256 digest of snapshot body vs `localStorage`; `visibilitychange` refresh when alerts on; iOS PWA note in error copy when permission denied.

### Tasks — Dashboard UX enhancements (client-only; no market APIs)

*Each task: snapshot JSON + browser UX only unless noted; no CoinGecko/CMC/Polygon from the client.*

- [x] **Q10.** **New / dropped since last visit:** persist last `schema_version` and symbol set in `localStorage`; show banner or row badges for **new** vs **dropped** coins vs previous snapshot.  
  - **Verification:** Simulated two JSON versions in dev; UI updates correctly; no network beyond snapshot URL.
  - **Notes:** Keys **`qualified_dash_prev_symbols_json`**, **`qualified_dash_prev_schema_version`**; first visit shows no diff; **`#diffBanner`** + **New** row badge. Service worker **`CACHE_VERSION`** bumped with dashboard static edits.

- [x] **Q11.** **Sort & filter:** client-side sort on columns (e.g. rank, 30d gain, uniformity, health); optional filter chips (e.g. “health ≥ N”).  
  - **Verification:** Sort order toggles correctly on mobile width; no extra fetches.
  - **Notes:** Sortable column headers + **Health ≥** chips in **`docs/dashboard/`**; service worker **`CACHE_VERSION`** bumped.

- [x] **Q12.** **Symbol search:** filter table rows by symbol/name substring (debounced input).  
  - **Verification:** Large list remains responsive; snapshot fetched once per poll cycle only.
  - **Notes:** **`#searchInput`** debounced **250ms**; filters client-side list only.

- [x] **Q13.** **Expandable row / drawer:** tap row to expand full backtest strategy table / fields from JSON (Telegram caption parity in data, not necessarily HTML).  
  - **Verification:** Collapsed by default; expand/collapse keyboard-accessible.
  - **Notes:** `docs/dashboard/app.js` — `tr.coin-row` + detail row; `field_set` **full** snapshot includes `backtest_top_strategies` / `backtest_buy_hold` from `utils/scan_artifacts.py`; SW **`CACHE_VERSION`** bumped with static assets.

- [x] **Q14.** **Last updated + stale warning:** display `updated_at` (humanized) and optional countdown to next expected scan; banner if snapshot age **> 2×** nominal `SCAN_INTERVAL_SECONDS` (config constant matching worker).  
  - **Verification:** Mock old `updated_at` shows warning; fresh snapshot clears it.
  - **Notes:** Top-level **`scan_interval_seconds`** on snapshot (from `Settings.scan_interval_seconds` / env override); dashboard `#staleBanner` + humanized meta line; older JSON without the field uses **3600s** fallback.

- [x] **Q15.** **Dark / light theme:** respect `prefers-color-scheme`; optional toggle with `localStorage` persistence.  
  - **Verification:** Toggle survives reload; contrast acceptable on OLED.
  - **Notes:** `docs/dashboard/` — CSS variables on `html[data-theme]`; **`qualified_dash_theme`** values **`system` \| `light` \| `dark`**; **`#themeCycleBtn`** cycles; **`#themeColorMeta`** updates for toolbar tint; SW cache bumped with static edits.

- [x] **Q16.** **Export current view:** button downloads **CSV** and/or **JSON** of filtered in-memory rows (client-generated).  
  - **Verification:** File opens in spreadsheet app; no server upload.
  - **Notes:** **`#exportCsvBtn`** / **`#exportJsonBtn`**; same filtered+sorted order as the table.

- [x] **Q17.** **Deep links:** support `#symbol=BTC` (or query param) to scroll/highlight row on load; update hash on row focus if product-appropriate.  
  - **Verification:** Shared URL focuses correct row after load.
  - **Notes:** **`?symbol=`** and **`#symbol=`**; **`history.replaceState`** on row focus; temporary **`.row-highlight`**; **`hashchange`** refreshes highlight.

- [x] **Q18.** **Reduced motion & accessibility:** `prefers-reduced-motion` respected; visible focus; semantic `<table>` or equivalent roles; labels for rank/gain cells for screen readers.  
  - **Verification:** Keyboard-only navigation through list; spot-check with axe or Lighthouse a11y.
  - **Notes:** **`prefers-reduced-motion`** in **`styles.css`**; **`caption.visually-hidden`**; **`th scope="col"`** + **`headers`** on cells; **`aria-sort`** on sortable headers; **`aria-label`** on sort buttons; focus rings on interactive controls.

- [x] **Q19.** **Optional chart thumbnail:** if snapshot row includes optional `chart_image_url` (HTTPS, worker-generated in **Q2** schema extension), show small image in expanded row; **hide** when field absent.  
  - **Verification:** Without URL field, no broken images; with mock URL, image loads (CORS on image host documented).
  - **Notes:** **`build_public_qualified_snapshot`** copies **`chart_image_url`** when **`https://`** ( **`field_set` full** ); dashboard detail block renders **`<img loading="lazy">`**; host must send **CORS** if cross-origin image.

- [x] **Q20.** **Scan health strip:** if snapshot includes optional `scan_duration_s`, `coins_evaluated`, `errors_count` (from worker in **Q2**), show read-only strip; **hide** when fields absent.  
  - **Verification:** Minimal snapshot still renders; extended snapshot shows strip.
  - **Notes:** `main.py` passes wall-clock duration, `len(all_symbols)`, and the sum of **`metrics.get_summary()` `errors`** counts into **`write_public_qualified_snapshot`**; dashboard **`#healthStrip`**; schema updated; SW **`CACHE_VERSION`** bumped.

- [x] **Q21.** **Tier-B Web Push:** minimal **Render** (or other) endpoint: store `pushSubscription` JSON per client (privacy policy required), VAPID keys in env, send **one** Web Push after each scan when subscriptions exist (payload: “Scan updated” + link to dashboard). Document rate limits and **no** market data in push body.  
  - **Verification:** Test push received on at least one browser after scan hook; unsub flow works; **H0** confirms no extra CoinGecko calls from push path.
  - **Notes:** `push_server/app.py` (Flask + `pywebpush`, `gunicorn`); `render.yaml` second web service + worker env `WEB_PUSH_*`; `main.py` `_maybe_notify_web_push_scan()`; dashboard **`#pushTierBBtn`** + `__PUSH_API_BASE__` / `__VAPID_PUBLIC_KEY__`; `docs/dashboard/sw.js` **`push`** / **`notificationclick`**, **`CACHE_VERSION`** v10; `docs/WEB_DASHBOARD.md` Tier-B section.

---

## Risks, follow-ups & operational checklist

This section captures **residual risks** and **ops actions** called out after H4 / H6 / J2 / Q2 work. It does not replace milestone tasks; it centralizes what product and ops should verify on a live worker.

### 6.1 H0 baseline and H6 “≥50% CoinGecko reduction” evidence

| Step | Action |
|------|--------|
| 1 | Freeze a **reference `config.json`** (or Render-mounted equivalent): same `TOP_COINS_LIMIT`, `TARGET_EXCHANGES`, `SCAN_INTERVAL_SECONDS`, `TOP_COINS_PROVIDER`, cache TTLs. |
| 2 | Run **one full scan** (or wait for the hourly worker). Copy the **`metrics.report()` / `metrics.json`** block (or log line) showing **`coingecko_http_*`** totals — label it **Baseline**. |
| 3 | After any tuning deploy (H1–H4), repeat on the **same config** without changing cadence. Copy totals — label it **After**. |
| 4 | Compute **delta %** on `coingecko_http_total` (and per-family rows if disputes arise). Store both blocks under **Milestone H0 Notes** or here as a dated sub-bullet. |
| 5 | **Qualification guardrail:** compare **final qualified count** and alert volume; if they diverge materially from baseline, treat the run as regression investigation before signing H6. |

Until steps 2–4 exist in writing, **H6 remains “measurement pending”** even though engineering work is merged.

### 6.2 CMC API tier vs tertiary OHLCV (H4)

| Risk | Mitigation |
|------|------------|
| **Hourly/daily OHLCV** from CoinMarketCap may be **disabled, rate-limited, or shallow** on the lowest commercial/free tiers ([CMC API pricing](https://coinmarketcap.com/api/pricing)). | Confirm your plan includes **historical OHLCV** where you rely on tertiary CMC. |
| Parser or HTTP **403/429** yields **empty tertiary**; pipeline correctly falls back to **CoinGecko → Polygon** only. | On Render, grep or tail worker logs for **`cmc_api`** / **`cmc_cache`** in `ohlcv_source` vs **`none`**. If `cmc_*` never appears, CMC is not contributing—**upgrade CMC** or accept **CG+Polygon-only** behavior. |
| **Daily CMC leg** uses **close-only** history synthesized into OHLC when full candles are unavailable—uniformity/backtests may differ slightly vs true exchange OHLC. | Compare a few symbols against CG when disputes arise; document acceptable variance with stakeholders. |

### 6.3 Optional scan artifacts (J2 heartbeat, Q2 public snapshot)

| Setting | Default | When to enable |
|---------|---------|----------------|
| `SCAN_HEARTBEAT_ENABLED` | `false` | When an external monitor (or human) should read **`DATA_DIR` / `SCAN_HEARTBEAT_FILE`** after each successful scan. |
| `PUBLIC_QUALIFIED_SNAPSHOT_ENABLED` | `false` | When a static dashboard (Milestone **Q4+**) will **`fetch()`** the JSON from a URL that serves **`PUBLIC_QUALIFIED_SNAPSHOT_FILE`**. |
| `SCAN_COSTS_ENABLED` | `false` | When **`DATA_DIR` / `SCAN_COSTS_FILE`** should receive per-scan Polygon/CMC/CG counts and cache summaries (J3). |
| `CMC_SLUG_MAP_ENABLED` / `CMC_SLUG_MAP_MAX_AGE_HOURS` | `true` / `72` | When **`CMC_API_KEY`** is set, refresh **`CMC_SLUG_MAP_CACHE_FILE`** from **`/v1/cryptocurrency/map`** if missing or stale; persist **`CMC_SLUG_LEARN_FILE`** for **gecko_id → cmc_slug** (Milestone **G8**). |

**Follow-ups**

- **Disk:** both files live under **`DATA_DIR`** (Render: `/var/data`). Ensure disk budget and **artifact hygiene** (`ARTIFACT_*`) remain sufficient if you add large snapshots.
- **Secrets:** snapshot builder **must not** embed API keys or Telegram tokens; today’s payload is **notification-shaped fields only**—re-audit when extending schema (**Q3**).
- **Provider load:** snapshot write is **serialization only** (no extra market HTTP); if a future host adds **dynamic** fields, re-check **Non-regression guardrail 7**.

### 6.4 Public snapshot exposure (Q2 / Q3)

| Risk | Mitigation |
|------|------------|
| JSON may be **world-readable** if you expose it via a public URL. | Omit sensitive fields (**Q3**); use **CORS** allowlist when wiring **Q5**; prefer **private network** or **signed URLs** if product requires. |
| **PII / strategy leakage** if rows include more than marketing agreed. | Review `utils/scan_artifacts.build_public_qualified_snapshot` before widening fields. |

### 6.5 GitHub branch protection (Milestone A4)

| Step | Action |
|------|--------|
| 1 | Repo **Admin** → **Settings** → **Branches** → **Add rule** for `main`. |
| 2 | Require status check **`verify`** (or the exact name shown on green **`ci.yml`** runs). |
| 3 | Optionally require **up-to-date branches** before merge. |
| 4 | Document completion date under **Milestone A4 Notes** (no secrets). |

### 6.6 Remaining engineering scope (pointer)

Outstanding milestones are still listed in **Progress summary** and in **Master execution order**: e.g. **I2** (further `main.py` splits), **L4–O**, optional **D3**, **A4** (settings, not code). Use this section for **risks and ops**; use milestone checkboxes for **delivery**.

---

## Progress summary (for humans)

| Milestone | Theme | Status |
|-----------|--------|--------|
| A | CI + Render guardrails | **A1–A2** done; **A4** needs GitHub admin (branch protection) |
| B | Exceptions | Complete |
| C | Telegram robustness | Complete |
| D | Pins + Ruff/Mypy | Complete (**D3** mypy optional) |
| E | Cross-platform | Complete |
| F | Logging | Complete |
| G | CMC links in Telegram | Complete (**G8** CG→CMC slug map + cache) |
| H | CoinGecko usage reduction | **H0–H6** complete (H6 % proof measurement pending) |
| I | DB docs / main split | **I1** done; **I2** in progress (first `scanner/` extract) |
| J | Observability & operations | **J1–J4** done (costs + degrade opt-in; JSON logs env-gated) |
| K | Telegram & UX | **K1–K4** done (quiet hours, exchange keyboard links, optional still-qualifying edit) |
| L | Data & strategy | **L0–L3** done; **L4** pending |
| M | Engineering quality | **M1** pytest, **M2** pre-commit, **M3** compose smoke |
| N | Security & compliance | **N1** Gitleaks in CI (**push protection** still admin); **N2** pending |
| O | Product & research | Not started |
| P | Backtesting modularization (web reuse) | **P1–P4** done |
| Q | Public dashboard + PWA + notifications + UX (**Q1–Q21**) | **Q1–Q21** done |

_Update the Status column as milestones complete (e.g. “Complete”, “In progress”)._

**Execution kickoff:** Complete **A1** and **A2** first; enable **A4** branch protection once CI is green. Skim **Master execution order** and **Technical reference** before touching scanner code (**G** onward).

**Note:** The former **Feature backlog** (six topic groups) is **Milestones J–O**. **P–Q** cover modular backtests and the public dashboard (**Q1–Q21** task IDs).

---

## Appendix — Key files reference

| Area | Files |
|------|--------|
| CI gate + CoinGecko H0 counters | `scripts/check_github_ci.py`, `utils/coingecko_usage.py`, `utils/metrics.py` (report section) |
| Gain filter (L0) | `main.py` FILTER 1; `GAIN_FILTER_MIN_*` in `config/settings.py` |
| OHLCV min bars (L1) | `OHLCV_MIN_*` in `config/settings.py`; `backtesting/data_loader.py` |
| Symbol quality line (L2) | **`NOTIFICATION_SYMBOL_QUALITY_LINE`**; `notifications/formatter.py` |
| Watchlist export (L3) | **`WATCHLIST_EXPORT_*`**; `utils/watchlist_export.py`; `main.py`; `scripts/export_watchlist.py` |
| Telegram diagnostics (K1) | `telegram_bot.py`; **`SCANNER_DIAG_COMMANDS_ENABLED`** in `config.json` |
| Telegram URLs | `notifications/formatter.py`, `notifications/telegram.py`, `database/models.py`, `main.py`, `api/coingecko.py`, `utils/cmc_slug_resolver.py`, `api/coinmarketcap.py` (CMC map) |
| OHLCV chain (CG → Polygon → CMC) | `api/coingecko.py`, `backtesting/data_loader.py`, `api/price_history_fallback.py`, `main.py` (uniformity / price paths), `database/cache.py` |
| CMC usage | `api/coinmarketcap.py`, `config/settings.py` |
| Render | `render.yaml`, `scripts/run_render_worker.sh` |
| Backtest library surface | `backtesting/*` (incl. `params.py` P2), `docs/BACKTESTING_LIBRARY.md` (Milestone P) |
| Public dashboard + PWA + UX | `main.py` (writer + optional Tier-B notify), `DATA_DIR/qualified_public_snapshot.json`, `push_server/`, `docs/WEB_DASHBOARD.md`, `docs/dashboard/*` (Milestone **Q1–Q21**) |
| Docker compose smoke (M3) | `docker-compose.yml` (root) |
| Scan costs (J3) | `utils/scan_costs.py`, `utils/provider_http_usage.py`, `SCAN_COSTS_*` in `config/settings.py` |
| CMC resolve + web push + active ranking + weekly digest + anomaly + enrichment + market/quiet/runtime init (I2 steps) | `scanner/cmc_resolve.py`, `scanner/web_push_notify.py`, `scanner/active_ranking.py`, `scanner/weekly_digest.py`, `scanner/anomaly_alerts.py`, `scanner/top_coin_resolution.py`, `scanner/coin_enrichment.py`, `scanner/market_processing.py`, `scanner/quiet_hours.py`, `scanner/runtime_init.py` |
| Risks & ops (H0 proof, CMC tier, artifacts, A4) | **Section 6** in this file |
