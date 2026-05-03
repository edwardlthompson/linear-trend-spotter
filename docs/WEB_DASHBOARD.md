# Public qualified-coin dashboard (Milestone Q)

For **Telegram vs website-only delivery** (snapshots, env vars, Render), see **[DELIVERY_MODE.md](DELIVERY_MODE.md)**.

## Data source

The static UI under `docs/dashboard/` loads **only** the JSON snapshot written by the Render worker (`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`, `PUBLIC_QUALIFIED_SNAPSHOT_FILE`). Browsers must **not** call market APIs.

## Local preview

From the repo root, serve the dashboard folder and pass the snapshot URL (any HTTPS or local file server that returns JSON):

```bash
cd docs/dashboard
python -m http.server 8765
```

Open `http://localhost:8765/?api=https%3A%2F%2Fyour-snapshot-relay.example%2Fqualified_public_snapshot.json` (use the **snapshot relay** GET URL, not the background worker).

## Dashboard UI extensions

See [`DASHBOARD_ROADMAP.md`](DASHBOARD_ROADMAP.md): exchange column + filter, 7d / vol acceleration, Tier-A notifications scoped to **filtered** rows, name-click **modal** for backtest JSON. Snapshot (`field_set` **`full`**) must include `listed_on`, `exchange_volumes`, acceleration fields — implemented in `utils/scan_artifacts.build_public_qualified_snapshot`.

**Sort & filters (refresh-safe):** Column sort, **Health ≥** chips, **Search**, and **Exchanges** (multi-select: Coinbase, Kraken, MEXC — matches scanner `TARGET_EXCHANGES`) are stored in **`localStorage`** (`qualified_dash_ui_*` keys, exchanges as `qualified_dash_ui_exchanges_json`) and restored on load. Theme and **Alert poll** interval were already persisted separately.

**Tier-A notifications** compare the **fully filtered** qualified list (including exchange checkboxes) between polls, so e.g. only **Coinbase**-listed rows can trigger “New / Out” alerts when that filter is active.

## GitHub Pages (Q6)

1. Build or copy `docs/dashboard/*` to the Pages branch or `/docs` site root.
2. At build time, inject the public snapshot URL (e.g. environment variable expanded into `config.js`, or keep using the `?api=` query parameter).
3. **No secrets** in the repo: snapshot URL is public by definition; use **`PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET`: `minimal`** in worker `config.json` if you want a smaller payload (Q3).

## CORS (Q5)

The origin that hosts `index.html` (e.g. `https://YOURNAME.github.io`) must be allowed by **`Access-Control-Allow-Origin`** on the HTTP response that serves `qualified_public_snapshot.json`.

**Recommended:** deploy **`snapshot_server/`** from root [`render.yaml`](render.yaml) (`linear-trend-spotter-snapshot`). It sends **`Access-Control-Allow-Origin`** (default `*`) on **`GET /qualified_public_snapshot.json`**, **`GET /relay-health`**, and **`POST /internal/ingest-snapshot`** for the worker. Set **`QUALIFIED_SNAPSHOT_RELAY_URL`** and **`QUALIFIED_SNAPSHOT_RELAY_SECRET`** on the worker (same secret as on the relay). Background workers do **not** serve HTTP.

**Operator health:** **`GET /relay-health`** returns JSON (`schema_version`, `has_snapshot_file`, `last_successful_ingest_at`, `last_ingest_http_status`, ingest byte size, `last_error`). The dashboard fetches the same origin path as your snapshot URL with the filename replaced by **`relay-health`** (or set **`window.__RELAY_HEALTH_URL__`** in `config.js`), after each successful snapshot load, and shows a short strip so you can spot a stale relay or failed worker POST without opening DevTools.

Alternatively, configure CORS on another HTTPS host (static headers, reverse proxy, object storage). Set **`Cache-Control: public, max-age=`** to slightly under your `SCAN_INTERVAL_SECONDS` so repeat visitors do not refetch every second.

## PWA and notifications (Q7–Q9)

Implemented under `docs/dashboard/`:

- **Manifest & icons:** `manifest.webmanifest`, `icons/icon-192.png`, `icons/icon-512.png` (regenerate with `python scripts/gen_dashboard_pwa_icons.py` if you change sizes or colors).
- **Service worker:** `sw.js` — static shell **cache-first**; same-origin `*.json` **network-only**. Cross-origin snapshot URLs (typical Render/GitHub setup) are **not** handled by this SW, so the qualified list is never served from an asset cache. After editing cached files, bump **`CACHE_VERSION`** inside `sw.js` so clients drop old caches.
- **Tier-A alerts:** **Enable update alerts** in the UI requests notification permission, registers the SW, then polls the snapshot URL on the interval you choose in **Alert poll** — **1h, 2h, 3h, 4h, 6h, 8h, 12h, or 1D** (TradingView-style steps; default **1h**). The choice is stored in `localStorage` as `qualified_dash_poll_interval_ms`. The tab also rechecks when it becomes visible again (`visibilitychange`). A **SHA-256** digest of the snapshot body is compared to the previous fetch (`qualified_dash_last_snap_digest`); on change, **`registration.showNotification`** is used when the SW is active.
- **iOS Safari:** Web Notifications are limited; users often need **Add to Home Screen** and a user gesture. The dashboard shows a short hint if permission is not granted.

### Tier-B Web Push (Q21)

Off-device alerts use a **small relay** (`push_server/` on Render or elsewhere), **not** the scanner worker. The worker only does **one** `POST` per successful scan to `/internal/notify-scan` when `WEB_PUSH_NOTIFY_URL` and `WEB_PUSH_INTERNAL_SECRET` are set (**no** CoinGecko or other market calls on that path). The push **body** is fixed copy plus a **dashboard URL** from `WEB_PUSH_DASHBOARD_URL` — **no** market data or coin list in the notification payload.

**Relay service**

- Deploy from repo root `push_server/` (see root `render.yaml` blueprint fragment `linear-trend-spotter-push`).
- Env on the relay: **`VAPID_PRIVATE_KEY`**, **`VAPID_CONTACT_EMAIL`** (mailto claim), **`WEB_PUSH_INTERNAL_SECRET`** (Bearer for internal notify), optional **`WEB_PUSH_SUBSCRIBE_TOKEN`** (Bearer or JSON `token` on subscribe/unsubscribe), **`WEB_PUSH_CORS_ORIGINS`** (e.g. `*` or your GitHub Pages origin), **`PUSH_SUBSCRIPTIONS_FILE`** (default JSON on disk — **ephemeral** on free web unless you add persistent disk).
- Generate keys, for example: `npx web-push generate-vapid-keys` ([web-push-libs](https://github.com/web-push-libs/web-push)) — put **public** key in dashboard `config.js` as `window.__VAPID_PUBLIC_KEY__`, **private** only on the relay.

**Worker**

- Set **`WEB_PUSH_NOTIFY_URL`** to the relay origin (no path), **`WEB_PUSH_INTERNAL_SECRET`** to the same value as on the relay, and **`WEB_PUSH_DASHBOARD_URL`** to the page users should open (e.g. your GitHub Pages qualified dashboard URL).

**Dashboard**

- When `window.__PUSH_API_BASE__` and `window.__VAPID_PUBLIC_KEY__` are set (see `docs/dashboard/config.example.js`), **Enable remote scan push** appears; it registers a push subscription with the relay and toggles off to unsubscribe. Service worker **`sw.js`** handles **`push`** and **`notificationclick`** (cache version bumped with static edits).

**Privacy / rate**

- Subscriptions are **endpoint URLs and keys** stored by your relay — disclose in your privacy policy if you ship this to users.
- **Rate:** at most **one** relay request per completed scan per worker; the relay sends **at most one** push per stored subscription per notify call (no client-driven burst).

## New / dropped since last visit (Q10)

The dashboard compares the current snapshot symbol set to the previous successful load (`localStorage`). A status banner summarizes **new** and **dropped** symbols and any **`schema_version`** change; rows that are new since the last visit show a **New** badge. Clear site data for the origin to reset the baseline.

## Sort, health filter, and search (Q11–Q12)

Column headers sort the in-memory table (toggle direction on repeat clicks). **Health ≥** chips filter by `health_score`. The search box filters symbols and names (substring, debounced). All are client-side only; the snapshot JSON is still fetched on the same cadence as before (Load button + optional 15-minute alerts).

## Theme, export, deep links, a11y, chart thumb (Q15–Q19)

- **Theme:** **Theme** cycles **system** (follows `prefers-color-scheme`), **light**, and **dark**; choice is stored as `qualified_dash_theme` in `localStorage`. The `<meta name="theme-color" id="themeColorMeta">` tag updates for mobile browser chrome.
- **Export:** **Export CSV** / **Export JSON** download the **current filtered and sorted** row set only; nothing is uploaded.
- **Deep links:** Append **`#symbol=BTC`** or **`?symbol=BTC`** (symbol only) to focus and briefly highlight a row after data loads; focusing a coin row updates the hash via **`replaceState`** (no extra history entries).
- **Accessibility:** Table **`caption`** (visually hidden), sortable **`aria-sort`**, header **`scope`/`id`** and cell **`headers`**, **`prefers-reduced-motion`** in CSS, visible **`:focus-visible`** on controls.
- **Chart image:** If a coin includes **`chart_image_url`** (`https://` only, optional in **`field_set: full`** snapshot), the expanded row shows a lazy-loaded image. Cross-origin images must allow this origin (**`Access-Control-Allow-Origin`**) or the image may fail to paint in the browser.

## Scan health strip (Q20)

When the worker writes **`scan_duration_s`**, **`coins_evaluated`**, and/or **`errors_count`** on the snapshot (enabled with **`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`** and a non-empty qualified list), the dashboard shows a read-only **`#healthStrip`** below the stale banner. Older or hand-made JSON without these keys leaves the strip hidden.
