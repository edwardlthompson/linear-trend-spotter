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
6. Progress summary & appendix  

---

## Non-regression & scope guardrails (mandatory for all milestones)

These rules apply to **every** milestone unless a task explicitly says otherwise and product approves a behavior change.

1. **Same scan universe:** Do **not** reduce the number of coins considered vs current behavior for the same `config.json` / env. In particular, do **not** lower `TOP_COINS_LIMIT`, drop exchanges from `TARGET_EXCHANGES`, or narrow the listing universe as a way to save API credits—unless a **separate, explicitly approved** product milestone exists. Internal optimizations (bulk requests, better caching, deduped calls) must preserve **≥** the same candidate set as today.
2. **Same scan interval:** Do **not** change `SCAN_INTERVAL_SECONDS` (Render), cron schedule, or worker timing as part of this plan. Cadence stays **identical** unless a dedicated ops/product change is approved outside this document.
3. **Additive by default:** New features (Milestones **J–Q**) must be **disabled or no-op** until opt-in via config/env, **or** must reproduce current outputs when the flag is off. No silent removal of notifications, backtests, or qualification stages in default configuration.
4. **No regression gate:** After each milestone, existing **verify** scripts in CI (Milestone A) and any milestone-specific verification must pass. For scan-touching work, document in Notes: same key counts as baseline (e.g. symbols loaded, final qualified count within expected variance for a fixed seed run if applicable).
5. **OHLCV chain unchanged in priority:** Per **Authoritative OHLCV policy** (Technical reference)—never swap provider order to save cost.
6. **Public dashboard (Milestone Q):** Snapshot serialization must **not** add provider HTTP calls; it only mirrors data already computed in the scan.

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
6. **Render:** After changes merge to the branch Render tracks (usually `main`), confirm the dashboard shows a successful deploy when applicable. Do not mark deploy-dependent tasks complete if the build failed on Render.

**Checkbox format:** Use exactly `- [ ]` (incomplete) and `- [x]` (complete) so searches and parsers stay consistent.

---

## Master execution order (phases A–Q)

Follow this order unless a task explicitly allows parallel work. **Prerequisite:** Render repo/branch confirmed (**A1**) before relying on auto-deploy for any milestone.

| Phase | Milestones | Purpose |
|-------|------------|---------|
| **1 — CI & core hardening** | **A → B → C → D → E → F** | Automated checks, exceptions, Telegram HTTP safety, pins/ruff, cross-platform dev, logging. **A2** CI should exist before broad refactors (**I2**, **M1**). |
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
| `backtesting/data_loader.py` `_get_or_fetch_1h` | Cache → **CG** → cache → **Polygon** | **No CMC tertiary yet** for hourly—add in **H4** if CMC API supports the need on your plan. |
| `backtesting/data_loader.py` `_get_or_fetch_1d_coingecko` | **CG** only | Extend with Polygon → CMC for daily if CG fails (H4). |
| `api/price_history_fallback.py` `get_30d_prices` | **Polygon** → **CMC** | Used where CG is already applied upstream in `main.py`; document call sites so the **global** story remains CG → Polygon → CMC. |

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

1. **Telegram links → CoinMarketCap** (Milestone G): **Zero API impact**—URLs only. Prefer `slug` → `https://coinmarketcap.com/currencies/{slug}/`; ensure `slug` is populated when using CMC-backed metadata.
2. **Operational (within guardrails):** Tune **caches** (`CACHE_PRICE_HOURS`, `CACHE_GECKO_ID_DAYS`) only where staleness remains acceptable **and** qualification outputs match baseline runs; **do not** reduce `TOP_COINS_LIMIT` or scan interval for savings (see Non-regression section).
3. **Architecture:** Prefer **bulk** CoinGecko endpoints where one call returns many coins instead of per-coin calls; ensure SQLite OHLCV cache (`database/cache.py`) is checked **before** repeating the same CG request.
4. **Do not** use “Polygon-first” or “CMC-first” for OHLCV to save credits; use **cache hits**, **bulk endpoints**, **mapper/list cadence**, and optional **`TOP_COINS_PROVIDER=cmc`** for **universe/listing** metadata only (same universe size)—keeping **CG → Polygon → CMC** for bars.
5. **Tertiary CMC:** Wire CMC OHLCV only **after** Polygon fails in loaders that still lack it (see **H4**).

Re-verify quotas on official docs before large refactors.

---

## Milestone A — Render pipeline & CI gate

**Goal:** Merges to `main` stay deployable; Render continues **auto-deploy on commit** (`render.yaml`: `autoDeployTrigger: commit`).

### Tasks

- [ ] **A1.** Confirm in Render Dashboard: service linked to correct **repo** and **branch**, **Auto-Deploy** enabled.  
  - **Verification:** Screenshot or written confirmation in Notes (not committed secrets).
- [x] **A2.** Add `.github/workflows/ci.yml`: Python **3.11**, `pip install -r requirements.txt`, run `python scripts/verify_backtest_env.py`.  
  - **Verification:** Actuator: push branch, workflow green; locally mirror commands.
- [ ] **A3.** (Optional) Add `ruff check .` with `pyproject.toml` `[tool.ruff]` once Ruff is introduced (may align with Milestone D).  
  - **Verification:** CI job passes.
- [ ] **A4.** GitHub **branch protection** on `main`: require the CI check before merge.  
  - **Verification:** Repo settings documented in Notes.

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

- [ ] **D1.** Add `pyproject.toml` with `[tool.ruff]` (target Py 3.11, sensible excludes for `scripts/` if needed).  
  - **Verification:** `ruff check .` passes in CI/local.
- [ ] **D2.** Pin `requirements.txt` (via `pip freeze` from clean 3.11 env or `pip-tools`).  
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

- [ ] **F1.** Migrate runtime modules (`config/settings.py`, `database/cache.py`, `utils/metrics.py`, `utils/rate_limiter.py`, etc.) to `logging` with consistent logger names.  
  - **Verification:** Run one full scan dry-run or worker start; logs appear without losing warnings.
- [ ] **F2.** Document convention: CLI `scripts/*.py` may keep `print` or use dedicated loggers.  
  - **Verification:** README or short comment in `utils/logger.py` Notes.

---

## Milestone G — Telegram: CoinMarketCap links (not CoinGecko)

**Goal:** User-facing links in Telegram notifications and keyboards prefer **CoinMarketCap** coin pages.

### Tasks

- [ ] **G1.** Add `MessageFormatter._build_cmc_url(coin: dict) -> str` (slug → `https://coinmarketcap.com/currencies/{slug}/`; optional fallback by symbol search URL if product accepts).  
  - **Verification:** Manual test with dict containing `slug` only / `slug`+`gecko_id` / neither.
- [ ] **G2.** `format_entry`: ensure header `<a href>` uses **CMC URL** when `slug` or `cmc_url` exists; do not prefer `_build_coingecko_url` for display. Align with `source_url` policy in `main.py` if needed.  
  - **Verification:** Generated HTML caption shows `coinmarketcap.com` link.
- [ ] **G3.** `format_exit`: replace `gecko_url` / `_build_coingecko_url` with CMC-first link line.  
  - **Verification:** Exit message contains CMC URL when slug present.
- [ ] **G4.** `notifications/telegram.py` (`_build_context_keyboard`, `send_exit_alert`): use CMC URL builder instead of `_build_coingecko_url` for “Analyze Coin” / source links.  
  - **Verification:** Keyboard URL opens CMC in browser.
- [ ] **G5.** `database/models.py` `_build_source_url`: reorder or adjust so **CMC slug URL** is preferred over CoinGecko when `slug` is available (consistent DB-derived links with Telegram).  
  - **Verification:** History insert path produces `cmc_url`/stored URL matching policy; no regression on coins without slug.
- [ ] **G6.** `main.py` / `api/coingecko.py` `source_url` assignments: when slug exists from CMC path, set **`https://coinmarketcap.com/currencies/{slug}/`** instead of CoinGecko coin page for notification-facing `source_url`.  
  - **Verification:** End-to-end scan with `TOP_COINS_PROVIDER=cmc` produces CMC `source_url` on sample coin.
- [ ] **G7.** Update `linear-trend-spotter-spec.md` or README notification section if spec still mandates CoinGecko links.  
  - **Verification:** Doc grep shows CMC as primary user link.

---

## Milestone H — Reduce CoinGecko usage (~50%) on free tier

**Goal:** Measurable drop in CoinGecko successful calls per scan cycle without breaking qualification/backtests.

### Tasks

- [ ] **H0. Measurement (do first)**  
  - Add lightweight **counters or structured logs** (per scan): CoinGecko requests by endpoint family (markets, OHLCV, mapper, tickers). Log to existing metrics file or `app_logger` summary line at scan end.  
  - **Verification:** One scan produces a numeric summary; baseline saved in Notes.

- [ ] **H1. Cache & config tuning (low risk, no universe/interval change)**  
  - Tune `CACHE_PRICE_HOURS` / `CACHE_GECKO_ID_DAYS` only with **before/after qualification comparison** on a fixed config (same `TOP_COINS_LIMIT`, same exchanges, same `SCAN_INTERVAL_SECONDS`); ensure `BACKTEST_RESUME_ENABLED` avoids duplicate heavy fetches. **Do not** reduce coin universe or interval.  
  - **Verification:** H0 metrics improve; qualified-coin counts / alert cardinality within agreed tolerance vs baseline (document in Notes).

- [ ] **H2. Bulk vs per-coin**  
  - Audit `api/coingecko.py` and `main.py` for redundant per-coin calls; consolidate to list/markets endpoints where possible.  
  - **Verification:** H0 metrics show fewer calls for same universe size.

- [ ] **H3. Provider mix (universe vs OHLCV)**  
  - Document and test Render env: e.g. `TOP_COINS_PROVIDER=cmc` for **top-coin / listing** pulls while **OHLCV remains CG → Polygon → CMC** per canonical chain.  
  - **Verification:** Full scan completes; backtest stage still meets minimum pass rate defined in runbook.

- [ ] **H4. Align all OHLCV paths with CG → Polygon → CMC**  
  - Audit `main.py` (uniformity / 30d paths), `backtesting/data_loader.py`, and `api/price_history_fallback.py`; document each call site in the Appendix table.  
  - Implement **CMC as explicit third step** where missing (e.g. hourly/daily after Polygon fails), gated on `CMC_API_KEY` and endpoint capability; do **not** reorder ahead of CoinGecko.  
  - **Verification:** `scripts/verify_backtest_data.py` (or agreed subset) passes; logs show fallback order when CG is stubbed or forced to fail in a dev test.

- [ ] **H5. Mapper refresh cadence**  
  - `CoinGeckoMapper.fetch_coingecko_list`: ensure full list refresh is not triggered too often (configurable interval or “stale after N days”).  
  - **Verification:** Logs show list fetch frequency matches new policy.

- [ ] **H6. Final**  
  - Confirm **≥50%** reduction vs H0 baseline **or** document why not achievable on free tier (then narrow scope: e.g. paid CG tier or acceptable product limits).  
  - **Verification:** Before/after numbers in Notes; stakeholder summary in this file (short paragraph under H).

---

## Milestone I — Database clarity & `main.py` modularization (lower priority)

### Tasks

- [ ] **I1.** Document `Database.execute` transaction semantics; consider `PRAGMA journal_mode=WAL` where missing for write-heavy DBs.  
  - **Verification:** Doc + optional stress note only.
- [ ] **I2.** Split `main.py` into modules (pipeline stages) in incremental PRs.  
  - **Verification:** CI + import smoke tests pass; behavior unchanged with default config (non-regression).

---

## Milestone J — Observability & operations

*Promoted from former backlog § “Observability & operations.” Must satisfy **Non-regression** defaults.*

### Tasks

- [ ] **J1.** **Structured JSON logging** (optional dual output): one JSON line per major event alongside existing human-readable logs; off by default or env-gated.  
  - **Verification:** With feature off, log output matches prior shape; with on, valid JSON lines; `compileall`.

- [ ] **J2.** **Heartbeat / health artifact:** write a small JSON file to `DATA_DIR` (or fixed path) after each successful scan (timestamp, duration, status)—no change to scan logic.  
  - **Verification:** File appears after run; interval and universe unchanged.

- [ ] **J3.** **Scan cost dashboard:** extend `scanner_insights.json` or add `scan_costs.json` with CG/Polygon/CMC call counts and cache hit rates (can build on H0 counters).  
  - **Verification:** Artifact valid JSON; scan completes; counts non-decreasing for same work (no dropped coins).

- [ ] **J4.** **Graceful degradation (opt-in only):** env flag e.g. `DEGRADE_SKIP_BACKTEST_ON_CG_CREDITS=0` default; when enabled and credits below threshold, skip backtest with explicit Telegram notice. **Default must preserve full pipeline.**  
  - **Verification:** Default off → identical stages vs baseline; on → documented behavior only.

---

## Milestone K — Telegram & UX enhancements

*Promoted from former backlog § “Telegram & UX.” All bot additions must be **additive**; default polling/commands unchanged when disabled.*

### Tasks

- [ ] **K1.** **`/health`**, **`/last`**, **`/cost`** (or similar) read-only commands in `telegram_bot.py` reading persisted metrics/heartbeat; feature flag default **off** or commands no-op until enabled.  
  - **Verification:** Flag off: no behavior change for existing flows; flag on: commands return expected text.

- [ ] **K2.** **Quiet hours:** config window (UTC) suppressing non-critical alerts; **entries/critical unchanged** when disabled; default = no quiet hours.  
  - **Verification:** Default config sends same alerts as today; quiet window suppresses only configured classes.

- [ ] **K3.** **Per-exchange deep links** in formatter/keyboard (Coinbase/Kraken/MEXC) **in addition to** CMC link; no removal of existing buttons.  
  - **Verification:** Manual Telegram check; links resolve.

- [ ] **K4.** **Message edit** path for “still qualifying” (optional): use `editMessageText` only when config enabled; default off.  
  - **Verification:** Default off: message volume unchanged vs baseline.

---

## Milestone L — Data & strategy extensions

*Promoted from former backlog § “Data & strategy.” Defaults must match current min bars and notification content.*

### Tasks

- [ ] **L1.** **Configurable OHLCV min bars** per timeframe in `config.json` with validation in `settings.py`; **defaults equal current hardcoded behavior.**  
  - **Verification:** Default config → same skip/pass rates as before on `verify_backtest_*` sample.

- [ ] **L2.** **Symbol quality score** line in notifications (data age, provider mix); additive field; can be hidden via config defaulting to current look.  
  - **Verification:** Default hides or matches “no extra line” per product choice; no dropped alerts.

- [ ] **L3.** **Watchlist export** (CSV/JSON) on schedule or command; writes to `DATA_DIR`; no change to core scan.  
  - **Verification:** Export file valid; scan unaffected.

- [ ] **L4.** **Backtest A/B shadow:** second profile on subset, logs only, **no Telegram** unless opt-in; default off.  
  - **Verification:** Off → no extra runtime; on → logs only, same primary alerts.

---

## Milestone M — Engineering quality

*Promoted from former backlog § “Engineering quality.”*

### Tasks

- [ ] **M1.** **`pytest`** suite: migrate or wrap `scripts/verify_*.py` assertions into tests; golden-file tests for `MessageFormatter` HTML output.  
  - **Verification:** `pytest` green in CI; existing verify scripts still runnable.

- [ ] **M2.** **Pre-commit:** `.pre-commit-config.yaml` with `ruff` + `compileall` (or `ruff` only if compileall covered by CI).  
  - **Verification:** `pre-commit run --all-files` passes.

- [ ] **M3.** **`docker compose`** (optional) local profile with `PYTHON_VERSION`, `DATA_DIR`, and Render env keys as optional blanks.  
  - **Verification:** `docker compose config` valid; README one-liner.

---

## Milestone N — Security & compliance

*Promoted from former backlog § “Security & compliance.”*

### Tasks

- [ ] **N1.** **Secret scanning:** enable GitHub push protection; add `gitleaks` (or `trufflehog`) job in CI on PR.  
  - **Verification:** CI job passes on clean repo; documented false positives.

- [ ] **N2.** **Telegram webhook mode (optional):** config to use webhook instead of long polling; **default remains long polling** (Render-compatible).  
  - **Verification:** Default: existing worker behavior; webhook path documented separately if not used on Render.

---

## Milestone O — Product & research (optional, larger scope)

*Promoted from former backlog § “Product / research.” Each sub-feature **default off** until config enables.*

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

- **Allowed imports (library tier):** `pandas`/`numpy`/`vectorbt` as today, `config.settings` only if refactored behind a **narrow interface** (prefer passing a `BacktestConfig` / plain dict from the host app).
- **Forbidden in library tier:** `notifications/*`, `telegram_bot.py`, `main.run_scanner` circular paths. Add a CI guard (import smoke or `ruff`/custom script) that fails if violated.
- **Outputs:** Typed or documented dicts / dataclasses consumable by HTTP layer later; optional thin `to_public_dict()` for API stability.

### Tasks

- [ ] **P1.** Document **`backtesting` public API** in `docs/BACKTESTING_LIBRARY.md`: entry points (`BacktestDataLoader`, `run_backtests_for_final_results`, `BacktestConfig`, `notification_rows_for_symbol`, engine/optimizer boundaries).  
  - **Verification:** Doc reviewed; list matches actual exports used by `main.py` today.

- [ ] **P2.** **Decouple settings:** replace or wrap direct `settings` singleton usage inside `backtesting/` where practical with **constructor-injected** limits (timeouts, workers, fee bps) so a web worker can construct loaders without full scanner config.  
  - **Verification:** `python -c "from backtesting.data_loader import BacktestDataLoader"` with a minimal test double or real `PriceCache` path unchanged for scanner.

- [ ] **P3.** **CI import guard:** script or test that imports `backtesting` package subtree and asserts no transitive import of `notifications`, `telegram_bot`, `main`.  
  - **Verification:** CI job fails if a forbidden import is introduced.

- [ ] **P4.** **Packaging stub (optional):** `pyproject.toml` `[project]` optional package name `linear-trend-backtest` pointing at `backtesting/` **or** documented `PYTHONPATH` layout for sibling repo.  
  - **Verification:** Second venv can `pip install -e .` (if packaged) or follow README “consume from sibling repo” without scanner.

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

- [ ] **Q1.** **JSON schema** (`docs/qualified_public_snapshot.schema.json` or markdown table): fields matching notification captions (symbol, name, gains, uniformity, health, rank fields, exchange volumes, provider volume, top backtest rows summary, `source_url`, timestamps, `schema_version`).  
  - **Verification:** Sample file hand-reviewed against one real Telegram payload.

- [ ] **Q2.** **Snapshot writer** in scanner completion path: build list from the **same** structure used for alerts; write atomically (`tmp` then rename); env e.g. `PUBLIC_QUALIFIED_SNAPSHOT=1`.  
  - **Verification:** With flag on, one scan produces valid JSON; with flag off, no file or no write; **provider call counts** (H0) unchanged vs baseline for same config.

- [ ] **Q3.** **Redaction / safety:** env or config for fields to omit on public JSON (e.g. internal debug); default keeps parity with notifications for allowed fields only.  
  - **Verification:** Redacted mode produces smaller JSON; no secrets in file.

- [ ] **Q4.** **Static dashboard:** responsive CSS, table or cards, reads JSON URL from `?api=` or baked `config.js` generated at deploy; empty state when `coins: []`.  
  - **Verification:** Manual load on narrow viewport; refresh shows updated list after next scan file update.

- [ ] **Q5.** **CORS + caching headers** on the GET that serves the snapshot (document in `docs/WEB_DASHBOARD.md`); document **hourly** expectation tied to `SCAN_INTERVAL_SECONDS`, not per-page cron.  
  - **Verification:** Cross-origin fetch from local static server succeeds; `max-age` present.

- [ ] **Q6.** **GitHub Pages wiring:** `docs/dashboard/` or `gh-pages` branch build instructions; **no secrets** in repo; JSON URL supplied via GitHub Actions env at build time **or** runtime fetch to public Render URL.  
  - **Verification:** Pages deploy succeeds; site loads without 4xx on JSON (use placeholder URL in CI if needed).

### PWA & browser notifications — design (tier A vs B)

| Tier | User experience | Extra backend? | Market APIs? |
|------|-----------------|---------------|--------------|
| **A (Q7–Q9)** | Installable app icon; optional **tab-open / PWA** notifications when snapshot **version** changes (poll JSON every 15–60 min + `visibilitychange`). | **None** | **None** (only your snapshot URL). |
| **B (Q21)** | Notifications when the browser has been closed for days. | **Yes** — Web Push relay (VAPID + subscription store) invoked after each scan. | **None** for market data. |

Implement **tier A** in **Q7–Q9** first; implement **tier B** in **Q21** (document VAPID, subscription storage, and ops in `docs/WEB_DASHBOARD.md`).

### Tasks — PWA & tier-A notifications

- [ ] **Q7.** **PWA shell:** add `manifest.webmanifest` (`name`, `short_name`, `start_url`, `display: standalone` or `minimal-ui`, `theme_color`, `background_color`); **maskable** and **192/512** icons; `<link rel="manifest">` + `theme-color` meta + **Apple** `apple-touch-icon` / `mobile-web-app-capable` where applicable.  
  - **Verification:** Lighthouse “PWA” or Chrome **Install app** succeeds on mobile + desktop; offline shell loads branded splash (even if data still requires network).

- [ ] **Q8.** **Service worker:** register from dashboard JS; **cache-first** for static assets (HTML/CSS/JS/icons); **network-only** (or short `networkTimeoutSeconds`) for the **snapshot JSON** so users never see stale qualified list from SW cache; bump **cache version** on deploy.  
  - **Verification:** Airplane-mode: UI shell loads; snapshot fetch fails gracefully with message; no market API calls; redeploy invalidates old asset cache.

- [ ] **Q9.** **Tier-A notifications:** explicit **“Enable update alerts”** button → `Notification.requestPermission()`; if `granted`, start **polling** snapshot URL on an interval **≥ 15 min** (configurable constant, aligned with hourly scan); compare `updated_at` / `schema_version` / hash to previous fetch → `registration.showNotification` (preferred from SW) or `new Notification` when changed; **silent** if permission `denied` or `default`; document **iOS Safari** limitations (user gesture, PWA to home screen).  
  - **Verification:** Grant + deny paths on Chrome Android + desktop; snapshot-only network traffic; `docs/WEB_DASHBOARD.md` references **Q21** for tier-B Web Push.

### Tasks — Dashboard UX enhancements (client-only; no market APIs)

*Each task: snapshot JSON + browser UX only unless noted; no CoinGecko/CMC/Polygon from the client.*

- [ ] **Q10.** **New / dropped since last visit:** persist last `schema_version` and symbol set in `localStorage`; show banner or row badges for **new** vs **dropped** coins vs previous snapshot.  
  - **Verification:** Simulated two JSON versions in dev; UI updates correctly; no network beyond snapshot URL.

- [ ] **Q11.** **Sort & filter:** client-side sort on columns (e.g. rank, 30d gain, uniformity, health); optional filter chips (e.g. “health ≥ N”).  
  - **Verification:** Sort order toggles correctly on mobile width; no extra fetches.

- [ ] **Q12.** **Symbol search:** filter table rows by symbol/name substring (debounced input).  
  - **Verification:** Large list remains responsive; snapshot fetched once per poll cycle only.

- [ ] **Q13.** **Expandable row / drawer:** tap row to expand full backtest strategy table / fields from JSON (Telegram caption parity in data, not necessarily HTML).  
  - **Verification:** Collapsed by default; expand/collapse keyboard-accessible.

- [ ] **Q14.** **Last updated + stale warning:** display `updated_at` (humanized) and optional countdown to next expected scan; banner if snapshot age **> 2×** nominal `SCAN_INTERVAL_SECONDS` (config constant matching worker).  
  - **Verification:** Mock old `updated_at` shows warning; fresh snapshot clears it.

- [ ] **Q15.** **Dark / light theme:** respect `prefers-color-scheme`; optional toggle with `localStorage` persistence.  
  - **Verification:** Toggle survives reload; contrast acceptable on OLED.

- [ ] **Q16.** **Export current view:** button downloads **CSV** and/or **JSON** of filtered in-memory rows (client-generated).  
  - **Verification:** File opens in spreadsheet app; no server upload.

- [ ] **Q17.** **Deep links:** support `#symbol=BTC` (or query param) to scroll/highlight row on load; update hash on row focus if product-appropriate.  
  - **Verification:** Shared URL focuses correct row after load.

- [ ] **Q18.** **Reduced motion & accessibility:** `prefers-reduced-motion` respected; visible focus; semantic `<table>` or equivalent roles; labels for rank/gain cells for screen readers.  
  - **Verification:** Keyboard-only navigation through list; spot-check with axe or Lighthouse a11y.

- [ ] **Q19.** **Optional chart thumbnail:** if snapshot row includes optional `chart_image_url` (HTTPS, worker-generated in **Q2** schema extension), show small image in expanded row; **hide** when field absent.  
  - **Verification:** Without URL field, no broken images; with mock URL, image loads (CORS on image host documented).

- [ ] **Q20.** **Scan health strip:** if snapshot includes optional `scan_duration_s`, `coins_evaluated`, `errors_count` (from worker in **Q2**), show read-only strip; **hide** when fields absent.  
  - **Verification:** Minimal snapshot still renders; extended snapshot shows strip.

- [ ] **Q21.** **Tier-B Web Push:** minimal **Render** (or other) endpoint: store `pushSubscription` JSON per client (privacy policy required), VAPID keys in env, send **one** Web Push after each scan when subscriptions exist (payload: “Scan updated” + link to dashboard). Document rate limits and **no** market data in push body.  
  - **Verification:** Test push received on at least one browser after scan hook; unsub flow works; **H0** confirms no extra CoinGecko calls from push path.

---

## Progress summary (for humans)

| Milestone | Theme | Status |
|-----------|--------|--------|
| A | CI + Render guardrails | Not started |
| B | Exceptions | Not started |
| C | Telegram robustness | Not started |
| D | Pins + Ruff/Mypy | Not started |
| E | Cross-platform | Not started |
| F | Logging | Not started |
| G | CMC links in Telegram | Not started |
| H | CoinGecko usage reduction | Not started |
| I | DB docs / main split | Not started |
| J | Observability & operations | Not started |
| K | Telegram & UX | Not started |
| L | Data & strategy | Not started |
| M | Engineering quality | Not started |
| N | Security & compliance | Not started |
| O | Product & research | Not started |
| P | Backtesting modularization (web reuse) | Not started |
| Q | Public dashboard + PWA + notifications + UX (**Q1–Q21**) | Not started |

_Update the Status column as milestones complete (e.g. “Complete”, “In progress”)._

**Execution kickoff:** Complete **A1** and **A2** first; enable **A4** branch protection once CI is green. Skim **Master execution order** and **Technical reference** before touching scanner code (**G** onward).

**Note:** The former **Feature backlog** (six topic groups) is **Milestones J–O**. **P–Q** cover modular backtests and the public dashboard (**Q1–Q21** task IDs).

---

## Appendix — Key files reference

| Area | Files |
|------|--------|
| Telegram URLs | `notifications/formatter.py`, `notifications/telegram.py`, `database/models.py`, `main.py`, `api/coingecko.py` |
| OHLCV chain (CG → Polygon → CMC) | `api/coingecko.py`, `backtesting/data_loader.py`, `api/price_history_fallback.py`, `main.py` (uniformity / price paths), `database/cache.py` |
| CMC usage | `api/coinmarketcap.py`, `config/settings.py` |
| Render | `render.yaml`, `scripts/run_render_worker.sh` |
| Backtest library surface | `backtesting/*`, `docs/BACKTESTING_LIBRARY.md` (Milestone P) |
| Public dashboard + PWA + UX | `main.py` (writer hook), `DATA_DIR/qualified_public_snapshot.json`, `docs/WEB_DASHBOARD.md`, `docs/dashboard/*` (Milestone **Q1–Q21**) |
