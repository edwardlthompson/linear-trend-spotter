# Public qualified-coin dashboard (Milestone Q)

## Data source

The static UI under `docs/dashboard/` loads **only** the JSON snapshot written by the Render worker (`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`, `PUBLIC_QUALIFIED_SNAPSHOT_FILE`). Browsers must **not** call market APIs.

## Local preview

From the repo root, serve the dashboard folder and pass the snapshot URL (any HTTPS or local file server that returns JSON):

```bash
cd docs/dashboard
python -m http.server 8765
```

Open `http://localhost:8765/?api=https%3A%2F%2Fyour-worker.example%2Fqualified_public_snapshot.json` (replace with your real snapshot GET URL).

## GitHub Pages (Q6)

1. Build or copy `docs/dashboard/*` to the Pages branch or `/docs` site root.
2. At build time, inject the public snapshot URL (e.g. environment variable expanded into `config.js`, or keep using the `?api=` query parameter).
3. **No secrets** in the repo: snapshot URL is public by definition; use **`PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET`: `minimal`** in worker `config.json` if you want a smaller payload (Q3).

## CORS (Q5)

The origin that hosts `index.html` (e.g. `https://YOURNAME.github.io`) must be allowed by **`Access-Control-Allow-Origin`** on the HTTP response that serves `qualified_public_snapshot.json`. Configure that on Render (static file headers) or a small read-only proxy. Set **`Cache-Control: public, max-age=`** to slightly under your `SCAN_INTERVAL_SECONDS` so repeat visitors do not refetch every second.

## PWA and notifications (Q7–Q9)

Implemented under `docs/dashboard/`:

- **Manifest & icons:** `manifest.webmanifest`, `icons/icon-192.png`, `icons/icon-512.png` (regenerate with `python scripts/gen_dashboard_pwa_icons.py` if you change sizes or colors).
- **Service worker:** `sw.js` — static shell **cache-first**; same-origin `*.json` **network-only**. Cross-origin snapshot URLs (typical Render/GitHub setup) are **not** handled by this SW, so the qualified list is never served from an asset cache. After editing cached files, bump **`CACHE_VERSION`** inside `sw.js` so clients drop old caches.
- **Tier-A alerts:** **Enable update alerts** in the UI requests notification permission, registers the SW, then polls the snapshot URL every **15 minutes** (and on `visibilitychange` when the tab wakes). A **SHA-256** digest of the snapshot body is compared to the previous fetch (`localStorage` key `qualified_dash_last_snap_digest`); on change, **`registration.showNotification`** is used when the SW is active.
- **iOS Safari:** Web Notifications are limited; users often need **Add to Home Screen** and a user gesture. The dashboard shows a short hint if permission is not granted.

Tier-B Web Push (**Q21**) still requires a separate subscription endpoint and is not covered here.

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
