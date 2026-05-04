# Deep analysis: CoinGecko vs CoinMarketCap vs Polygon in this codebase

This document maps **which provider is strongest for each pipeline stage**, how **symbol / slug / id** conflicts show up, where **caching** helps or hurts, and a **phased redesign** path for better budget use, scan time, and end-user signal quality—without assuming another paid subscription beyond the free/demo tiers you already use.

**Companion:** operational toggles and config keys live in [`COIN_API_CREDIT_STRATEGY.md`](./COIN_API_CREDIT_STRATEGY.md).

---

## 1. Scorecard: best tool per job (in *this* repository)

| Pipeline stage | Best primary | Why | Second line | Weak / avoid |
|----------------|-------------|-----|-------------|----------------|
| **Ranked universe + % gains (7d/30d…)** | **CMC** `listings/latest` | **One** HTTP call returns many assets with quote % — ideal for monthly call budgets | **CG** `/coins/markets` paged (250/req) if you must | Polygon is not a “top 4000” universe API here |
| **Stable coin id for CG-specific APIs** | **CoinGecko** `id` (e.g. `bitcoin`) | All CG routes use **gecko id**, not symbol | Mapper + `COINGECKO_ID_ALIASES` | Symbol-only matching is unsafe (collisions) |
| **Hourly OHLCV for 30d uniformity** | **Context-dependent** | **CMC** v2 OHLCV: one call per symbol, good bar count when it works. **Polygon** 1h aggs: strong for **USD pair** if `X:SYMUSD` exists. **CG** `market_chart` / hourly: broad id coverage, **bills per coin** | Order controlled by `OHLCV_UNIFORMITY_SOURCE_ORDER` | Same symbol on different networks / wrap edge cases |
| **Per-exchange 24h volume (venue column)** | **CoinGecko** `/coins/{id}/tickers` | **Only** source in-tree that returns **per-market / per-exchange** rows you can map to `TARGET_EXCHANGES` | None drop-in on CMC free tier for *same* venue breakdown | CMC “volume_24h” is **aggregate**, not venue split |
| **Intraday backtests / signal age / vol accel** | **BacktestDataLoader** order: **CG → Polygon → CMC** (see `backtesting/data_loader.py`) | Reuses same cache table; CG first for id-based fetch | Fallbacks when CG fails or cache miss | RAM cap on loader cache (50 entries) on small hosts |
| **Dashboard 7d/30d sparklines (`closes_1h`)** | **Local `ohlcv_cache` in scanner DB** | `attach_hourly_sparkline_closes_for_snapshot` **does not** call external APIs — it reads **cached** 1h rows by **symbol** | Freshness = whatever last wrote rows (uniformity / backtest paths) | If cache is stale, charts lag until something refetches OHLCV |
| **User-facing links (CMC page vs CG page)** | **CMC slug** when known | `CmcSlugResolver` + `gecko_id_to_cmc_slug.json` learns **gecko_id → cmc_slug** | CG URL from `gecko_id` | Wrong slug if learning map has an old pair |

**Bottom line:** There is **no single winner**. The design that minimizes cost while keeping features is **deliberate division of labor**: CMC for **bulk ranking**, CoinGecko for **ids + venues + CG-native charts**, Polygon as **OHLCV offload** where the pair exists, with a **single canonical identity** (below) to reduce cross-site mistakes.

---

## 2. Strengths and weaknesses (product + API reality)

### CoinGecko (Demo / Pro / public)

- **Strengths:** Universal **coin id**; **tickers** per exchange; **market_chart** hourly; large coverage; your app already instruments **`record_coingecko_http`** by route (`market_chart`, `tickers`, `markets`, …).
- **Weaknesses:** **Credits per successful call** on Demo/Pro; **paged** `/coins/markets` for big universes; **rate limits** tight on Demo; id space can differ from “ticker” mental model.

### CoinMarketCap (Basic free tier typical)

- **Strengths:** **Single** listings call for thousands of rows; **numeric CMC id** and **slug** for links; v2 **historical OHLCV** usable for hourly series when symbol resolves cleanly.
- **Weaknesses:** Monthly call caps; **symbol** queries can be ambiguous (multi-asset tickers); **no** in-repo replacement for **per-exchange** CG tickers; OHLCV quality vs CG can differ slightly (uniformity numbers may shift if you prefer CMC-first order).

### Polygon (aggregates)

- **Strengths:** Often **one** intraday request per symbol for `X:{SYM}USD` style aggs; good when list ≈ liquid US crypto equities style symbols.
- **Weaknesses:** **Not** a full symbol universe API for “top 4000”; naming is **ticker/pair** based—**bridged** or low-liquidity names may miss; adds another failure mode next to CG/CMC.

---

## 3. Identity, slugs, and cross-site conflicts

### 3.1 Canonical keys used in code today

- **Scanner coin row:** dominated by **`symbol` (upper)** + **`cg_id` / `gecko_id`** for anything CoinGecko.
- **CMC resolution:** `resolve_cmc_data` / `resolve_top_coin_data` match on **symbol**, **aliases**, and **normalized** symbol (`scanner/cmc_resolve.py`).
- **OHLCV SQLite cache:** keyed by **`(exchange, symbol, timeframe)`** where `exchange` is the **provider label** (`coingecko`, `polygon`, `cmc`) — see `database/cache.py`. Same **symbol** may exist across three rows with different sources.
- **Sparklines:** `_hourly_closes_from_scanner_db` aggregates by **`symbol` only** (merges duplicate timestamps across provider rows).

### 3.2 Conflict scenarios (realistic)

1. **Ticker collision:** Two different projects share **BTC**-style ticker on different listings; direct symbol match can attach the wrong CMC row. **Mitigation:** normalized + alias maps; prefer **unique ids** when merging providers.
2. **Gecko id vs CMC slug:** Different websites use different **slug** strings; the app learns **`gecko_id → cmc_slug`** (`utils/cmc_slug_resolver.py`) but a wrong learn persists until file/map refresh.
3. **Polygon `X:SYMUSD` vs CG id:** Polygon is **pair-based**; CG is **asset-id-based**. Same **symbol** might not be the same economic asset if unlisted on Polygon.
4. **Stale cache mixing sources:** If half the windows are from **CMC** and half from **CG**, uniformity and sparklines are **internally consistent per run** but **not** comparable to a “single-vendor truth.”

### 3.3 Design principles for a safer multi-vendor model

1. **Pick one canonical id for joins:** e.g. **`cg_id` as primary** (because tickers and venue data require it), plus **`cmc_id`** optional when `TOP_COINS_PROVIDER=cmc` supplies it.
2. **Never key external API calls on symbol alone** when ambiguity exists—use **id** (CG or CMC) or **disambiguation rules** (rank, market cap, or explicit alias table).
3. **Version the mapping tables** (`COINGECKO_ID_ALIASES`, `CMC_SYMBOL_ALIASES`, `gecko_id_to_cmc_slug.json`) in git or artifact backups so bad learns are revertible.
4. **Log resolution path** (already partially done via resolution_type strings) into scanner insights for debugging wrong coin attachment.

---

## 4. Caching: what you have vs “smarter” hourly refresh for active coins

### 4.1 Current behavior (short)

- **`CACHE_PRICE_HOURS`:** Max age for **OHLCV rows** in `get_ohlcv_rows` — same TTL for **all** coins in the uniformity fetch path.
- **`cache_price_data(cg_id)`:** Short-circuits **uniformity** if price/uniformity already computed for that **gecko id** (not symbol-only).
- **Sparklines:** Read **DB cache** only — **no** automatic “tail refresh” for qualified coins unless a pipeline step **rewrote** `ohlcv_cache` recently.

### 4.2 Tension with your goal

You want: **less redundant bulk pull**, but **hourly freshness on charts for active (qualified) coins**. Those imply **different TTL policies**:

| Tier | Suggested policy | Rationale |
|------|-------------------|-----------|
| **Exploration / long-list** | Longer TTL or CMC-first OHLCV | Most coins fail filters; cheap paths ok |
| **Gain-qualified pipeline** | Moderate TTL | Balance CPU vs API |
| **Final qualified / watchlist** | **<= scan interval** for last **N** bars | Sparklines and decisions match “this hour” |

### 4.3 Smarter caching (redesign directions — no code here yet)

1. **Split config:** `CACHE_PRICE_HOURS_EXPLORATION` vs `CACHE_PRICE_HOURS_QUALIFIED` (or derive qualified set after gain filter).
2. **Incremental OHLCV merge:** Instead of refetching 30d hourly every time, fetch only **missing tail hours** from the chosen provider (requires per-provider “last ts” in DB).
3. **Sparkline refresh job:** After scan writes snapshot, **one** cheap CG `market_chart` with **`days=2`** & hourly interval **only** for `final_results` symbols — keeps charts tight without re-pulling full month for everyone. *Credits:* fewer total points but extra endpoint calls; tune vs Demo plan.
4. **Provider tag on coin:** Persist `ohlcv_source` on the snapshot row so the dashboard can show **“CMC / CG / Polygon”** per coin—better **decisions** for users.

---

## 5. Redesign roadmap (optional phases)

### Phase A — Config & ops (low risk)

- `TOP_COINS_PROVIDER=cmc`, `OHLCV_UNIFORMITY_SOURCE_ORDER=cmc,polygon,coingecko`.
- Tune caches; monitor **`api_cost_panel`** and **`scanner_insights`**.
- Document **symbol collision** cases in your alias files when you see mis-linked coins.

### Phase B — Identity & telemetry (medium)

- Add **`cmc_id`** (numeric) to internal coin dict when from CMC listings; join maps using **id** where APIs allow.
- Expand **insights** JSON: counts by `ohlcv_source`, resolution outcomes, cache hit rate.

### Phase C — Tiered cache + tail refresh (medium–high)

- Implement **split TTLs** + optional **tail-only** fetch for qualified set.
- Align **`SCAN_INTERVAL_SECONDS`** with sparkline max age so dashboard and scanner agree.

### Phase D — Unified “market data” facade (high, largest payoff)

- Single module that chooses provider per **task type** (universe / ohlcv / venue volume / link slug) with **explicit cost estimates** and **fallback chain**.
- Enables future features: **cross-check close** (CG vs CMC last hour), **venue integrity score**, without scattering HTTP logic.

---

## 6. Accuracy vs budget tradeoffs (honest)

- **Single-vendor OHLCV** is easiest to reason about; **multi-vendor** saves money but introduces **reconciliation** questions.
- **Venue volumes** will remain **CoinGecko-heavy** unless you invest in **exchange-native APIs** (new integrations—not “free tier only”).
- **Faster scans** usually mean **less work per coin** (smaller universe, stronger early filters, or **better caching**)—not magic.

---

## 7. What to read next in this repo

| Topic | Location |
|-------|----------|
| OHLCV fetch order (uniformity) | `scanner/uniformity_stages.py`, `OHLCV_UNIFORMITY_SOURCE_ORDER` in `config/settings.py` |
| Backtest loader chain | `backtesting/data_loader.py` |
| CMC slug learning | `utils/cmc_slug_resolver.py` |
| Sparklines from DB | `scanner/coin_enrichment.py` — `attach_hourly_sparkline_closes_for_snapshot` |
| Credit strategy toggles | [`COIN_API_CREDIT_STRATEGY.md`](./COIN_API_CREDIT_STRATEGY.md) |

---

*This is a living architecture note: adjust as CoinGecko/CMC/Polygon tiers and endpoints change.*
