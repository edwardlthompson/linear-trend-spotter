# Manual steps (dashboard + API budget)

Short checklist after pulling recent changes. Nothing here runs automatically on GitHub Pages until a **new snapshot JSON** exists with the new fields.

## 1. Deploy the scanner (Render / worker / wherever it runs)

1. Push or deploy the branch that includes the latest `main.py`, `utils/vendor_api_quota.py`, and `utils/scan_costs.py`.
2. Confirm the service has the same env vars as before, especially:
   - `COINGECKO_API_KEY` (Pro or `CG-…` demo) — needed for CoinGecko `/api/v3/key` usage when quota fetch is enabled.
   - `CMC_API_KEY` — needed for CoinMarketCap `/v1/key/info` usage.
3. Wait for **one full scan** to finish so it writes `qualified_public_snapshot.json` again.

## 2. Optional: turn off vendor quota HTTP calls

Each scan performs up to **two** extra GETs (CoinGecko + CMC), not counted in your in-app HTTP metrics. To disable:

- Set env `SCAN_COST_VENDOR_QUOTA_FETCH=false` (or `0` / `no` / `off`).

## 3. Point the dashboard at live JSON

- **Relay:** ensure `docs/dashboard/config.js` (or `?api=`) still points at your Render snapshot URL.
- **GitHub Pages only:** either keep using the relay URL, or run your repo’s snapshot sync script after a scan and push the updated JSON (static `docs/` snapshot will not update by itself).

## 4. Refresh the browser / PWA

1. Open the dashboard, then **hard refresh** (Ctrl+F5 / clear cache for the site).
2. If the UI looks stale (old icons or old JS), unregister the service worker once (DevTools → Application → Service Workers → Unregister) or bump is automatic when `sw.js` `CACHE_VERSION` changes after deploy.

## 5. Volumes / watchlist / charts (from earlier changes)

- **Coinbase 24h volume:** fixed server-side (ticker pagination). New volumes appear after a **new scan** and a snapshot that includes `exchange_volumes`. Stale rows can persist until **exchange volume cache TTL** expires on the worker (or wipe that cache if you need an immediate refresh).
- **Watchlist:** pins are now **`SYMBOL|exchange`** (e.g. `BTC|coinbase`). Legacy symbol-only pins migrate once when you load a snapshot; you can remove extra venues from the watchlist after migration.
- **7d chart:** only renders when the snapshot has **≥ 168** hourly closes in `closes_1h`; otherwise the cell shows `—`.

## 6. API budget bars

- **Vendor credits (CoinGecko / CMC):** bars use **`vendor_quota`** from the snapshot when the worker could read `/key` usage and keys are set.
- **Configured HTTP caps:** still used when set (`SCAN_COST_PANEL_*` in config); if both vendor quota and a cap exist, the UI explains both.
- **Polygon:** there is no documented public REST for monthly credits in this pipeline; Polygon still uses your configured cap + local `polygon_http_*` counts.
