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

## PWA and notifications

See Milestone **Q7–Q9** in `docs/EXECUTION_PLAN.md`. Tier-B Web Push (**Q21**) requires a separate subscription endpoint and is not covered here.
