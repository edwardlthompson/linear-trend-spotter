# CoinGecko / CoinMarketCap credit strategy (no paid tier required)

**Deep dive:** provider fit per pipeline stage, slug/id conflicts, caching tiers, and redesign phases — see [`API_PROVIDER_DEEP_ANALYSIS.md`](./API_PROVIDER_DEEP_ANALYSIS.md).

The scanner can **split API load** between providers that already ship **free or demo** tiers. Nothing here removes features (filters, OHLCV uniformity, backtests, exchange volumes, dashboard fields): it only changes **which HTTP call runs first** or **which bulk endpoint builds the coin universe**.

## Where credits go today

| Stage | Typical CoinGecko usage | Alternative already in code |
|-------|-------------------------|-----------------------------|
| **Universe + gains** (`TOP_COINS_LIMIT`) | Many `/coins/markets` pages (250 coins per page) | **One** `GET /v1/cryptocurrency/listings/latest` from **CoinMarketCap** |
| **Hourly OHLCV for uniformity** | One `/coins/{id}/market_chart` or hourly OHLC per qualified coin | **CMC** hourly OHLCV (`get_cmc_hourly_ohlcv`), **Polygon** aggregates, then CG |
| **Per-exchange 24h volume** (`exchange_volumes`) | `/coins/{id}/tickers` per coin | Still CoinGecko today (CMC global volume ≠ venue breakdown) |

The largest **easy** CoinGecko saver is usually switching the **top-coins provider**. Hourly OHLCV is the next lever once `CMC_API_KEY` (free Basic, ~10k calls/month — verify on [CMC pricing](https://coinmarketcap.com/api/pricing/)) and optionally `POLYGON_API_KEY` are set.

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

- **`COINGECKO_CALLS_PER_MINUTE`** — align with your Demo plan (often **30** RPM).
- **`CMC_CALLS_PER_MINUTE`** — stay under CMC Basic limits.

## 5. What we did **not** change

- **Exchange ticker volumes** still use CoinGecko `/coins/{id}/tickers` so **per-venue** `exchange_volumes` and dashboard filters stay intact.
- **Backtesting** `backtesting/data_loader.py` keeps its own provider order; adjust there separately if you optimize batch backtests.

## Summary checklist

1. `TOP_COINS_PROVIDER`: **`cmc`** + `CMC_API_KEY`.
2. `OHLCV_UNIFORMITY_SOURCE_ORDER`: **`cmc,polygon,coingecko`** + `CMC_API_KEY` (+ optional Polygon key).
3. Increase **`CACHE_PRICE_HOURS`** / **`CACHE_GECKO_ID_DAYS`** cautiously.
4. Watch **`SCAN_COST_PANEL_*`** / dashboard metrics after deploy.
