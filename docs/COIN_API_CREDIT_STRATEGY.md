# CoinGecko / CoinMarketCap credit strategy (no paid tier required)

**Deep dive:** provider fit per pipeline stage, slug/id conflicts, caching tiers, and redesign phases — see [`API_PROVIDER_DEEP_ANALYSIS.md`](./API_PROVIDER_DEEP_ANALYSIS.md). **Slug/id translation across CG/CMC/Polygon:** [`CROSS_PROVIDER_IDENTITY.md`](./CROSS_PROVIDER_IDENTITY.md).

**Monthly usage math:** call-site formulas + scenario table — see [`API_MONTHLY_BUDGET_ESTIMATE.md`](./API_MONTHLY_BUDGET_ESTIMATE.md).

## Bulk / batching (fewer HTTP calls)

What is already bundled:

| Area | Behavior |
|------|----------|
| **CoinGecko universe** | `/coins/markets` pages of **250** coins per request (`get_top_coins_with_gains`). |
| **CoinGecko ID aliases** | **All** ids listed under `COINGECKO_ID_ALIASES` plus ids needed by exchange symbols → **chunked** `get_markets_rows_for_ids` (≤250 ids/request). Rare misses get a **second** bulk top-up before the gain filter. |
| **Alias fallback** | If a row is still missing, try **one-id** `get_markets_rows_for_ids` before `/coins/{id}`. |
| **Tickers (venue volume)** | **One** `get_tickers` chain per **distinct** `cg_id` (not per row); 24h cache. |
| **CMC universe** | **One** `listings/latest` call. CMC + fallback share a **single** RPM gate. |
| **Scan history DB** | `executemany` batch insert for qualified rows. |

What cannot be batched (provider limits): **per-coin** OHLCV (`market_chart` / Polygon aggs / CMC OHLCV). Mitigate with **cache TTLs** and provider order — see sections 2–3 above.

The scanner can **split API load** between providers that already ship **free or demo** tiers. Nothing here removes features (filters, OHLCV uniformity, backtests, exchange volumes, dashboard fields): it only changes **which HTTP call runs first** or **which bulk endpoint builds the coin universe**.

## Where credits go today

| Stage | Typical CoinGecko usage | Alternative already in code |
|-------|-------------------------|-----------------------------|
| **Universe + gains** (`TOP_COINS_LIMIT`) | Many `/coins/markets` pages (250 coins per page) | **One** `GET /v1/cryptocurrency/listings/latest` from **CoinMarketCap** |
| **Hourly OHLCV for uniformity** | One `/coins/{id}/market_chart` or hourly OHLC per qualified coin | **CMC** hourly OHLCV (`get_cmc_hourly_ohlcv`), **Polygon** aggregates, then CG |
| **Per-exchange 24h volume** (`exchange_volumes`) | `/coins/{id}/tickers` per coin | Still CoinGecko today (CMC global volume ≠ venue breakdown) |

The largest **easy** CoinGecko saver is usually switching the **top-coins provider**. Hourly OHLCV is the next lever once `CMC_API_KEY` and optionally `POLYGON_API_KEY` are set — verify whether **historical OHLCV** is allowed on your [CMC plan](https://coinmarketcap.com/api/pricing/) (Basic free is often **listings/map-only** for practical purposes); see [`API_MONTHLY_BUDGET_ESTIMATE.md`](./API_MONTHLY_BUDGET_ESTIMATE.md).

## 1. Use CoinMarketCap for the ranked universe (biggest CG reduction)

In `config.json`:

```json
"TOP_COINS_PROVIDER": "cmc"
```

Requirements:

- Set **`CMC_API_KEY`** (same env the scanner already uses).
- Keep **`COINGECKO_API_KEY`** for OHLCV, tickers, mapper, and aliases — you are **not** dropping CoinGecko from the pipeline.

Effect: **one** CMC listings call instead of **ceil(TOP_COINS_LIMIT / 250)** CoinGecko `/coins/markets` calls each scan.

## 2. Prefer CMC (then Polygon) before CoinGecko for uniformity OHLCV

After universe load, each coin still needs ~30d of hourly candles. Default order remains **`coingecko,polygon,cmc`** (backward compatible).

To spend **CoinGecko credits last**, set:

```json
"OHLCV_UNIFORMITY_SOURCE_ORDER": "cmc,polygon,coingecko"
```

Behavior:

- For each coin, the scanner tries **cache live API** in that order until hourly rows succeed.
- CoinGecko still runs when CMC (and Polygon if configured) cannot supply enough bars — **no feature removed**.
- Uniformity scores may differ slightly if CMC hourly bars differ from CoinGecko for some symbols; compare a dry run if you need identical numbers.

## 3. Stretch caches (fewer repeat HTTP calls)

Already in `config.json`:

- **`CACHE_PRICE_HOURS`** — longer TTL → fewer repeat OHLCV fetches when qualification windows overlap across scans.
- **`CACHE_GECKO_ID_DAYS`** — fewer `/coins/list` refreshes for the mapper.

Raise gradually so staleness stays acceptable for your `SCAN_INTERVAL_SECONDS`.

## 4. Rate limits (stay within free/demo RPM)

- **`COINGECKO_CALLS_PER_MINUTE`** — client pacing + 429 exponential backoff with optional `Retry-After` (`api/coingecko.py`).
- **`CMC_CALLS_PER_MINUTE`** — shared **`MinIntervalGate`** across **`CoinMarketCapClient`** and **`PriceHistoryFallback`** CMC calls (`scanner/runtime_init.py`) so listings + OHLCV respect one budget; 429/transient retries with backoff (`api/coinmarketcap.py`, `api/price_history_fallback.py`).
- **`POLYGON_CALLS_PER_MINUTE`** — separate gate for Polygon aggregates (default **5** RPM; raise if your Polygon plan allows more).

## 5. What we did **not** change

- **Exchange ticker volumes** still use CoinGecko `/coins/{id}/tickers` so **per-venue** `exchange_volumes` and dashboard filters stay intact.
- **Backtesting** `backtesting/data_loader.py` keeps its own provider order; adjust there separately if you optimize batch backtests.

## Summary checklist

1. `TOP_COINS_PROVIDER`: **`cmc`** + `CMC_API_KEY`.
2. `OHLCV_UNIFORMITY_SOURCE_ORDER`: **`cmc,polygon,coingecko`** + `CMC_API_KEY` (+ optional Polygon key).
3. Increase **`CACHE_PRICE_HOURS`** / **`CACHE_GECKO_ID_DAYS`** cautiously.
4. Watch **`SCAN_COST_PANEL_*`** / dashboard metrics after deploy.
