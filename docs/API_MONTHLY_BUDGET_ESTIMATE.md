# Estimated monthly API usage (this codebase)

This note ties **actual call sites in the repo** to **rough monthly credit math** so you can sanity-check provider tiers. **Official limits change** — re-check [CoinMarketCap API pricing](https://coinmarketcap.com/api/pricing/), [CoinGecko API pricing](https://www.coingecko.com/en/api/pricing), and your Polygon.io plan before relying on numbers.

**Convention:** Unless the provider documents otherwise, treat **1 successful HTTP GET = 1 credit** (CoinGecko documents “1 call = 1 credit”). Failed calls may still count on some APIs — monitor your dashboards.

---

## Baseline scan assumptions (defaults in repo)

| Input | Default | Source |
|--------|---------|--------|
| `SCAN_INTERVAL_SECONDS` | `3600` (hourly) | `config/settings.py` |
| `TOP_COINS_LIMIT` | `4000` | `config.json.example` |
| Uniformity **score** cache TTL | **6 hours** | `PriceCache.PRICE_CACHE_DURATION` in `database/cache.py` (`get_price_data` / `cache_price_data`) |
| OHLCV row cache max age | `CACHE_PRICE_HOURS` (e.g. `12`) | only applies **inside** `_fetch_hourly_ohlcv_for_uniformity` when the 6h score cache missed |
| Exchange volume cache | **24 hours** | `EXCHANGE_VOLUME_CACHE_DURATION` in `database/cache.py` |

**Scans per 30-day month (hourly):** \(S \approx 24 \times 30 = 720\) scans.

---

## 1. CoinMarketCap — where credits go

### 1a. `GET /v1/cryptocurrency/listings/latest` (bulk universe)

- **When:** `TOP_COINS_PROVIDER` is **`cmc`** (`api/coinmarketcap.py` → `get_all_coins_with_gains`).
- **How many:** **1 HTTP per scan** → **~720 / month**.

### 1b. `GET /v1/cryptocurrency/map` (slug resolution cache)

- **When:** `CMC_SLUG_MAP_ENABLED` and map file missing or older than `CMC_SLUG_MAP_MAX_AGE_HOURS` (`utils/cmc_slug_resolver.py` → paginated `fetch_cryptocurrency_map_page`).
- **How many:** **~⌈N/5000⌉ HTTP per full refresh**, with **~2.1 s** between pages (`time.sleep(2.1)` after each page).
- **Monthly:** about **`(720 / max_age_hours) × pages`**. Example: `max_age_hours = 72` → ~10 refreshes/month; if **N ≈ 10k** assets → **2 pages** → **~20 HTTP / month**. If you refresh daily or N grows past 5k often, scale up.

### 1c. `GET /v2/cryptocurrency/ohlcv/historical` (hourly OHLCV)

- **When:** `OHLCV_UNIFORMITY_SOURCE_ORDER` includes **`cmc`**, and for a coin the **6h uniformity cache missed**, then `cmc` **OHLCV cache** missed → `PriceHistoryFallbackClient.get_cmc_hourly_ohlcv` (`scanner/uniformity_stages.py`, `api/price_history_fallback.py`). Each attempt records HTTP (`record_cmc_http`).
- **How many (upper bound):** For each gain-qualified coin that stays in the pipeline, uniformity refetch happens about **once per 6 hours** → **~4 × 30 = ~120** CMC OHLCV calls **per coin per month** if **CMC always answers first** and you never short-circuit with cache.
- **Total OHLCV ballpark:** **≈ 120 × K**, where **K** = typical number of symbols that (a) pass gain filters, (b) have `cg_id`, and (c) take the CMC path on cache expiry **without** already having a 6h price-cache hit.

**Example K (steady-state):**

| K (coins) | Listings (~720) | Map (~20–30) | OHLCV (~120×K) | **CMC total / month** |
|-----------|------------------|--------------|----------------|------------------------|
| 20 | 720 | ~25 | ~2,400 | **~3.1k** |
| 50 | 720 | ~25 | ~6,000 | **~6.7k** |
| 80 | 720 | ~25 | ~9,600 | **~10.3k** |
| 100 | 720 | ~25 | ~12,000 | **~12.7k** |

Add **backtesting** and **data_loader** paths that hit CMC hourly/daily if you run large offline jobs — `backtesting/data_loader.py` can call `get_cmc_hourly_ohlcv` / daily quotes after CoinGecko/Polygon.

### 1d. Free “Basic” tier vs OHLCV

[CMC pricing](https://coinmarketcap.com/api/pricing/) currently lists **Basic (free)** as **15,000 call credits/mo** and states **no historical data** on that tier. **Historical OHLCV** may be unavailable or return errors on Basic; the app then falls back to Polygon/CoinGecko. You may still pay **attempt** credits if requests are counted regardless of body — confirm in your CMC usage dashboard.

**Implication:** Putting **`cmc` first** in `OHLCV_UNIFORMITY_SOURCE_ORDER` is only a CoinGecko saver if **hourly OHLCV is actually enabled** on your CMC plan. Otherwise you pay listings/map attempts while OHLCV stays empty.

---

## 2. CoinGecko — where credits go

Assumptions: **Demo/analyst** style plan with **monthly call credits** (see official pricing); **1 call = 1 credit**.

### 2a. Top universe when `TOP_COINS_PROVIDER` is **`coingecko`**

- **Endpoint:** `/coins/markets` at **250 coins per page** (`api/coingecko.py`).
- **Calls per scan:** **⌈TOP_COINS_LIMIT / 250⌉**. For 4000 → **16** calls.
- **Monthly:** **16 × 720 ≈ 11,520** (dominant line item if you stay on CG for the universe).

### 2b. Per-exchange tickers (venue volumes)

- **Code:** `hydrate_exchange_volumes_from_coingecko` (`scanner/listings_and_volumes.py`): **one `get_tickers` chain per distinct `cg_id`**, not per row; grouped with `defaultdict`. Cache **24h** per `cg_id`.
- **Monthly (rough):** **~30 × U × P**, where **U** = distinct qualified coins needing tickers in a typical month, **P** = average pages **1–12** per coin (pagination until `<100` tickers or `max_pages`). Often **P ≈ 1–2** if `exchange_ids` filter hits quickly.

### 2c. Hourly OHLCV (`market_chart` / hourly path)

- **When:** Uniformity path uses **`coingecko`** after cache miss **or** after CMC/Polygon per `OHLCV_UNIFORMITY_SOURCE_ORDER`.
- **Frequency:** Same **~120 refetches / coin / month** cap as CMC *when* CoinGecko is the provider that finally supplies bars and the 6h uniformity cache keeps expiring — but **24h exchange cache** and **6h score cache** reduce overlap with other stages.

**Order matters:** `cmc,polygon,coingecko` shifts spend from CG to CMC/Polygon when those succeed; `polygon,coingecko,cmc` minimizes CMC OHLCV attempts.

---

## 3. Polygon.io

- **Calls:** `get_polygon_30d_hourly_ohlcv` / daily aggregates — **typically 1 HTTP per symbol per fetch** when that provider runs (`api/price_history_fallback.py`, `record_polygon_http`).
- **Monthly:** Same structural formula as CMC OHLCV when Polygon is **second or first** in order and cache misses: **up to ~120 × K** **attempts** per month for always-qualified coins (hourly path), **plus** backtest/snapshot usage.
- **Plan bottleneck:** Many free/starter plans are **requests-per-minute** limited (e.g. low RPM). At **hourly scans with tens of coins**, **RPM** often bites before a “monthly credit” ceiling — tune concurrency and ordering so Polygon isn’t flooded after cache expiry.

---

## 4. Summary budget table (order-of-magnitude)

Use **K** = typical count of gain-qualified coins with `cg_id` moving through uniformity + tickers each month.

| API | Primary drivers | Example monthly range (hourly scans, K≈40–80) |
|-----|-----------------|--------------------------------------------------|
| **CMC** | Listings (720) + map (~25) + OHLCV (**~120×K** if cmc-first succeeds) | **~6k–11k+** before backtests; scales **linearly with K** if OHLCV hits CMC |
| **CoinGecko** | `/coins/markets` **~11.5k** if CG universe + tickers (~30×U×P) + OHLCV when CG fills gaps | Often **10k–50k+** depending on universe provider and P |
| **Polygon** | Hourly/daily aggs when used; **RPM-limited** | Highly variable; bounded by rate limit more than a monthly cap on many plans |

---

## 5. Mitigations (already aligned with repo design)

1. **`TOP_COINS_PROVIDER`: `"cmc"`** — drops **~11.5k/mo** CoinGecko `/coins/markets` calls (trades CG universe spend for **720** CMC listings calls).
2. **`OHLCV_UNIFORMITY_SOURCE_ORDER`** — **`polygon,coingecko,cmc`** minimizes **paid/rare CMC OHLCV** attempts if Polygon covers most symbols; **`cmc,polygon,coingecko`** saves CoinGecko credits **only if** CMC OHLCV is **included on your CMC plan** and returns data.
3. **Lengthen effective uniformity refresh** — today the hard gate is **6h `price_cache`**, not `CACHE_PRICE_HOURS`. Changing that requires a **code change** (or accepting staleness) if you want fewer refetches than 4/day/coin.
4. **Instrument** — enable **`SCAN_COSTS_ENABLED`** / dashboard **`api_cost_panel`** and compare to **`SCAN_COST_PANEL_*_MONTHLY_HTTP_CAP`** in config.

---

## 6. References in code

| Concern | Location |
|---------|-----------|
| CMC listings + map | `api/coinmarketcap.py` |
| CMC / Polygon OHLCV | `api/price_history_fallback.py` |
| Uniformity order + cache keys | `scanner/uniformity_stages.py`, `database/cache.py` |
| CG tickers (venue volume) | `scanner/listings_and_volumes.py`, `api/coingecko.py` |
| Backtest OHLCV chain | `backtesting/data_loader.py` |
