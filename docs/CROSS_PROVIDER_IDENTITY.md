# Cross-provider identity (CoinGecko ↔ CoinMarketCap ↔ Polygon)

Three vendors mean **three namespaces**: CoinGecko **`id`** (string slug), CoinMarketCap **`id`** (integer) + **`slug`** (URL), Polygon **`ticker`** (`X:{SYM}USD` for crypto aggregates here). **Ticker symbols alone are not globally unique.** This note is the operational contract for keeping qualified coins aligned across APIs.

**Related:** conflict scenarios and cache keys — [`API_PROVIDER_DEEP_ANALYSIS.md`](./API_PROVIDER_DEEP_ANALYSIS.md) §3.

---

## 1. Recommended canonical model (hub-and-spoke)

| Role | Canonical key | Why |
|------|----------------|-----|
| **Primary join key inside this app** | **`cg_id`** (CoinGecko coin id) | Almost every CoinGecko route requires it; tickers and mapper are keyed off it. |
| **Rankings / links when using CMC universe** | **`cmc_id`** + **`slug` / `cmc_slug`** | Listings supply stable CMC identifiers; `/currencies/{slug}/` URLs. |
| **Polygon intraday** | **Uppercase `symbol`** → `X:{symbol}USD` | Pair naming, not asset id; wrong if symbol is reused or non-USD listing. |

**Rule:** Treat **`symbol` as a display and Polygon shortcut**, not proof of identity. Prefer **`cg_id`** for CoinGecko HTTP and **`cmc_id`** (when present) for CMC HTTP that accepts ids. Use **name + symbol** when disambiguating collisions.

---

## 2. What the codebase already does (keep using)

| Mechanism | Purpose |
|-----------|---------|
| **`CMC_SYMBOL_ALIASES` / `COINGECKO_ID_ALIASES`** | Explicit overrides when automatic matching is wrong (`config/settings.py`). |
| **`resolve_cmc_data` + `normalize_symbol`** | Direct match → configured alias → single normalized candidate (`scanner/cmc_resolve.py`). |
| **`CmcSlugResolver`** | Cached **`/v1/cryptocurrency/map`** + **`gecko_id → cmc_slug`** learn file + **name** disambiguation when multiple rows share a ticker (`utils/cmc_slug_resolver.py`). |
| **`CoinGeckoMapper`** | Symbol → **`coingecko_id`** from `/coins/list` with local DB (`api/coingecko_mapper.py`). |
| **OHLCV cache keys** | `(exchange, symbol, timeframe)` — same symbol may exist under `coingecko` / `polygon` / `cmc` rows (`database/cache.py`). |

---

## 3. Main failure modes (design against these)

1. **Ticker collision** — Two assets share `ABC`; normalized lookup returns the wrong CMC row or mapper picks the wrong `cg_id`.
2. **Wrong learn file** — `gecko_id_to_cmc_slug.json` remembers a bad pair; it persists until corrected.
3. **Polygon ≠ asset** — `X:SYMUSD` might be thin, missing, or a different bridge/wrapper than the CoinGecko asset you scored.
4. **Mixed OHLCV sources** — Uniformity/scores remain internally consistent per run, but **cross-vendor** bars can disagree slightly; dashboards should not imply one vendor’s candle is another’s.

---

## 4. Suggested path forward (phased)

### Phase A — Operational rigor (low cost, immediate)

- **Prefer CMC ids when available:** If `TOP_COINS_PROVIDER=cmc`, persist **`cmc_id`** and **`slug`** on the coin dict early and thread them through enrichment (you already learn **gecko → cmc_slug**; numeric **id** is even safer for CMC-only calls).
- **Treat alias files as source control:** Keep **`CMC_SYMBOL_ALIASES`** and **`COINGECKO_ID_ALIASES`** reviewed when users report wrong coin links or OHLCV.
- **Log and monitor resolution:** Use existing **`resolution_type`** strings and scanner insights; alert when **`normalized`** or **`missing`** rates spike for high-value symbols.
- **Version / backup learns:** Copy **`gecko_id_to_cmc_slug.json`** before bulk edits; revert bad mappings quickly.

### Phase B — Stronger binding (medium effort)

- **Require `name` for disambiguation:** When **multiple** CMC or mapper candidates exist for a ticker, **do not guess** — require unique **name** match (already in `CmcSlugResolver`) or an **alias** entry.
- **Snapshot identity block:** On each qualified coin row in JSON/DB, write **`cg_id`**, **`cmc_id`** (if known), **`cmc_slug`**, **`polygon_ticker`** (e.g. `X:BTCUSD`), and **`identity_confidence`** (`direct` / `alias` / `learned` / `ambiguous_skipped`).
- **Optional sanity check:** Compare **last-hour close** or **24h %** from CG vs CMC when both exist; flag large divergence for manual alias review (not for blocking trades — for **data QA**).

### Phase C — Unified resolver (larger refactor, highest payoff)

- **Single `IdentityResolver`** module: inputs `(symbol, name?, gecko_id?, source_row)`; outputs **canonical bundle** + **confidence**; all HTTP entry points call it once per coin per scan.
- **Polygon gate:** Only call `X:{SYM}USD` when **`cg_id`** (or explicit config) says the asset is the expected **USD spot** representation; otherwise skip or use a configured **`POLYGON_TICKER_OVERRIDES`** map for edge cases.

### Phase D — UX

- **Dashboard / alerts:** Show **which id space** each metric came from (`ohlcv_source`, link domain). Helps users reason about “why this coin” when slugs differ across sites.

---

## 5. What not to do

- **Do not** key Polygon or CMC OHLCV on **raw symbol** alone when your pipeline already has **`cg_id`** — use ids + alias tables first.
- **Do not** silently overwrite **`gecko_id_to_cmc_slug`** learns from low-confidence matches; prefer **manual** alias or **name-unique** rows only.

---

## 6. Config knobs you already have

| Knob | Effect |
|------|--------|
| `TOP_COINS_PROVIDER` | `cmc` → CMC slugs/ids in universe; fewer CG markets calls. |
| `CMC_SLUG_MAP_*` | Map cache + learn file for CG-only universe paths. |
| `OHLCV_UNIFORMITY_SOURCE_ORDER` | Which vendor supplies bars (does not fix identity; keep aliases correct). |

---

*Review when adding a fourth data source: introduce an explicit **vendor column** and **id column per vendor** on internal coin records before wiring new HTTP.*
