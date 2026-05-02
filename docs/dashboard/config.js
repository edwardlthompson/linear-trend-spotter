/**
 * Public snapshot JSON. Not a secret — browsers fetch this URL.
 *
 * **Default (GitHub Pages):** same-origin file `docs/qualified_public_snapshot.json` → no CORS, no Render relay.
 * Update it after a scan: `python scripts/sync_snapshot_to_docs.py` then commit + push.
 *
 * **Optional remote relay:** set to `https://…-snapshot.onrender.com/qualified_public_snapshot.json` if you use
 * `snapshot_server/` + worker POST (see README). Or override with `?api=` on the dashboard URL.
 */
window.__SNAPSHOT_URL__ = "../qualified_public_snapshot.json";
