# Public qualified-coin dashboard (Milestone Q)

For **how snapshots reach this UI** (relay, env vars, Render), see **[DELIVERY_MODE.md](DELIVERY_MODE.md)**.

**Deploy / refresh / API budget:** step-by-step checklist → **[MANUAL_DEPLOY_STEPS.md](MANUAL_DEPLOY_STEPS.md)**.

## Data source

The static UI under `docs/dashboard/` loads **only** the JSON snapshot written by the Render worker (`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`, `PUBLIC_QUALIFIED_SNAPSHOT_FILE`). Browsers must **not** call market APIs.

Default URL is set in `docs/dashboard/config.js` (`window.__SNAPSHOT_URL__`) or overridden with **`?api=`** on the dashboard URL. A collapsible **Data source** control in the UI can expose URL/reload without cluttering the header.

## Local preview

From the repo root, serve the dashboard folder and pass the snapshot URL (any HTTPS or local file server that returns JSON):

```bash
cd docs/dashboard
python -m http.server 8765
```

Open `http://localhost:8765/?api=https%3A%2F%2Fyour-snapshot-relay.example%2Fqualified_public_snapshot.json` (use the **snapshot relay** GET URL, not the background worker).

## Current grid and columns

The **Qualified** and **Watchlist** tabs render a **single logical table** with these behaviors:

- **One row per coin per venue** for the scanner’s target exchanges (Coinbase, Kraken, MEXC): rows are derived from `listed_on` and/or `exchange_volumes` in the snapshot. The **Name** column shows the venue in parentheses (e.g. `Jito (Coinbase)`). **Exchange** shows the venue label; **24h vol** shows that venue’s approximate USD volume from `exchange_volumes`.
- **7d %** and **30d %** are numeric gain columns (sort keys `g7pct`, `g30pct`). **7d chart** and **30d chart** show `closes_1h` sparklines (high/low reference lines and orange last-close). Beside each chart, **% distance of last close below the window high** is shown; those columns sort independently (`g7hi`, `g30hi`).
- **Uniformity** and **Health** have header **minimum** filters (Health includes **≥ 60**, **≥ 65**, **≥ 70**). **Vol Δ%** has acceleration filters. **24h vol** has a **floor** filter: **≥ $100k**, **$500k**, **$1M**, **$10M** (applies to the row’s venue volume).
- **Exchange** header holds the **multi-select** checklist: no boxes checked = all venues; one or more checked = only rows whose **Exchange** matches a checked venue (row-level filter, not “coin listed on any of these”).
- **Backtest**: when the snapshot includes data, **Chart** / **Results** open links or a modal; there is no separate “expand row” sheet for OHLCV.

Snapshot **`field_set: full`** should include `listed_on`, `exchange_volumes`, `closes_1h`, gains, health, uniformity, and acceleration fields where you want charts and filters populated — built in `utils/scan_artifacts.build_public_qualified_snapshot`.

Future dashboard milestones are tracked in [`EXECUTION_PLAN.md`](EXECUTION_PLAN.md) (Milestone **Q**).

## Sort, filters, and persistence (refresh-safe)

Column sorts, **Health** / **Uniformity** / **Vol Δ%** / **24h vol** / **Exchange** filters, **search** query, **active tab**, **Tier-A poll interval**, and **theme** are stored in **`localStorage`** (`qualified_dash_ui_*` keys; exchanges as `qualified_dash_ui_exchanges_json`; volume floor as `qualified_dash_ui_vol_min_usd`) and restored on load.

The header **search** is width-capped (similar to a typical desktop search bar) and matches **symbol**, **name**, and **venue label** substrings (case-insensitive, debounced).

**Tier-A update alerts** (Settings → enable notifications + **Alert poll**) compare the **fully filtered view** between polls, including exchange and volume floor filters. The stored baseline is a JSON array of **row keys** `SYMBOL|exchangeId` (`qualified_dash_poll_filtered_rows_v2`), so duplicate symbols on different venues are tracked separately. A separate digest can fire a **“snapshot refreshed”** notification when the JSON body changes but the filtered row set does not.

## Logs and API budget

- **Logs** tab: scan / relay / regime strips (session-dismissible), stale snapshot banner, **`api_cost_panel`** (per-scan HTTP counts; CoinGecko/CMC **vendor credits** when keys allow `/key` fetches), and a **rolling operational log** (24h) persisted in **`localStorage`** so it survives refresh.
- **Settings** tab: duplicates the same **API usage & budget** panel when `api_cost_panel` is present, so meters are visible without opening Logs.

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

- **Manifest & icons:** `manifest.webmanifest`, PNG icons under `icons/`, optional **`icons/app-icon.svg`** as the primary **favicon** (`rel="icon"`). Regenerate PNGs with `python scripts/gen_dashboard_pwa_icons.py` if you change sizes or colors. **`launch_handler`** with **`client_mode: "navigate-existing"`** asks supporting browsers to reuse one desktop app window when possible.
- **Service worker:** `sw.js` — static shell **cache-first**; same-origin `*.json` **network-only**. Cross-origin snapshot URLs (typical Render/GitHub setup) are **not** handled by this SW, so the qualified list is never served from an asset cache. After editing cached files, bump **`CACHE_VERSION`** inside `sw.js` so clients drop old caches.
- **Tier-A alerts:** **Enable update alerts** requests notification permission, registers the SW, then polls the snapshot URL on the interval chosen in **Alert poll** — **1h, 2h, 3h, 4h, 6h, 8h, 12h, or 1D** (default **1h**). Stored as `qualified_dash_poll_interval_ms`. The tab also refetches when it becomes visible again (`visibilitychange`). Notifications use **`registration.showNotification`** with **absolute** `icon` / `badge` URLs (better on Android), optional vibration, filtered-row diff and/or body-digest “refresh” messaging, and `qualified_dash_last_poll_snapshot_digest` to avoid duplicate refresh toasts.
- **iOS Safari:** Web Notifications are limited; users often need **Add to Home Screen** and a user gesture. The dashboard shows a short hint if permission is not granted.

### Tier-B Web Push (Q21)

Off-device alerts use a **small relay** (`push_server/` on Render or elsewhere), **not** the scanner worker. When `WEB_PUSH_NOTIFY_URL` and `WEB_PUSH_INTERNAL_SECRET` are set, the worker does **at most one** `POST` per completed scan **only if** at least one coin **entered** or **exited** the qualified active list. The relay endpoint is still `/internal/notify-scan`. The push **title/body** are short human-readable lines (which symbols moved) plus **`WEB_PUSH_DASHBOARD_URL`** on click — **no** OHLCV or other market payloads.

**Relay service**

- Deploy from repo root `push_server/` (see root `render.yaml` blueprint fragment `linear-trend-spotter-push`).
- Env on the relay: **`VAPID_PRIVATE_KEY`**, **`VAPID_CONTACT_EMAIL`** (mailto claim), **`WEB_PUSH_INTERNAL_SECRET`** (Bearer for internal notify), optional **`WEB_PUSH_SUBSCRIBE_TOKEN`** (Bearer or JSON `token` on subscribe/unsubscribe), **`WEB_PUSH_CORS_ORIGINS`** (e.g. `*` or your GitHub Pages origin), **`PUSH_SUBSCRIPTIONS_FILE`** (default JSON on disk — **ephemeral** on free web unless you add persistent disk).
- Generate keys, for example: `npx web-push generate-vapid-keys` ([web-push-libs](https://github.com/web-push-libs/web-push)) — put **public** key in dashboard `config.js` as `window.__VAPID_PUBLIC_KEY__`, **private** only on the relay.

**Worker**

- Set **`WEB_PUSH_NOTIFY_URL`** to the relay origin (no path), **`WEB_PUSH_INTERNAL_SECRET`** to the same value as on the relay, and **`WEB_PUSH_DASHBOARD_URL`** to the page users should open (e.g. your GitHub Pages qualified dashboard URL).
- The worker POST includes each coin’s **`listed_on`** (plus inferred venues from exchange volumes on exits). The relay stores optional **`notify_exchanges`** from the dashboard subscribe body (same ids as the Exchanges checkboxes; **omit or empty array = all venues**). A subscriber who chose only **Kraken** will not receive a push for a coin that is **only** listed on MEXC.

**Dashboard**

- When `window.__PUSH_API_BASE__` and `window.__VAPID_PUBLIC_KEY__` are set (see `docs/dashboard/config.example.js`), **List change push** appears; it registers a push subscription with the relay and toggles off to unsubscribe. Service worker **`sw.js`** handles **`push`** and **`notificationclick`** (cache version bumped with static edits).

**Privacy / rate**

- Subscriptions are **endpoint URLs and keys** stored by your relay — disclose in your privacy policy if you ship this to users.
- **Rate:** at most **one** relay request per completed scan **when** there is entry/exit churn; the relay sends **at most one** push per stored subscription per notify call (no client-driven burst).

## New / dropped since last visit (Q10)

The dashboard compares the current snapshot symbol set to the previous successful load (`localStorage`). A status banner summarizes **new** and **dropped** symbols and any **`schema_version`** change; rows that are new since the last visit show a **New** badge. Clear site data for the origin to reset the baseline.

## Layout and deep links

- The main layout keeps header, tabs, and meta above a **scrollable table region**; **column headers are sticky** within that region so coin rows scroll underneath.
- **Deep links:** Append **`#symbol=BTC`** or **`?symbol=BTC`** (symbol only) to focus and briefly **highlight all rows** for that symbol after data loads; focusing a coin row updates the hash via **`replaceState`** (no extra history entries).

## Theme, export, a11y (Q15–Q19)

- **Theme:** **Theme** cycles **system** (follows `prefers-color-scheme`), **light**, and **dark**; choice is stored as `qualified_dash_theme` in `localStorage`. The `<meta name="theme-color" id="themeColorMeta">` tag updates for mobile browser chrome.
- **Export:** **Export** (CSV or JSON) downloads the **current filtered and sorted view**, including **per-venue rows**. CSV includes `row_exchange`, `row_vol_24h_usd`, and chart **% below window high** columns; JSON adds `dashboard_row_*` and `dashboard_chart_*` fields on each exported coin object (watchlist-only placeholder rows stay minimal).
- **Accessibility:** Table **`caption`** (visually hidden), sortable **`aria-sort`**, header **`scope`/`id`** and cell **`headers`**, **`prefers-reduced-motion`** in CSS, visible **`:focus-visible`** on controls.
- **Backtest chart image:** If a coin includes **`chart_image_url`** (`https://` only, optional in **`field_set: full`** snapshot), the modal may show a lazy-loaded image. Cross-origin images must allow this origin (**`Access-Control-Allow-Origin`**) or the image may fail to paint in the browser.

## Scan health strip (Q20)

When the worker writes **`scan_duration_s`**, **`coins_evaluated`**, and/or **`errors_count`** on the snapshot (enabled with **`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`** and a non-empty qualified list), the dashboard shows a read-only **`#healthStrip`** (Logs tab telemetry cluster). Older or hand-made JSON without these keys leaves the strip hidden.
