/**
 * Public snapshot JSON. Not a secret — browsers fetch this URL.
 *
 * **Default (GitHub Pages):** live Render snapshot relay, with the dashboard falling back to the
 * committed same-origin file `docs/qualified_public_snapshot.json` if the relay is unavailable.
 * Refresh the committed fallback after a scan with: `python scripts/sync_snapshot_to_docs.py` then commit + push.
 *
 * **Optional remote relay:** set to `https://…-snapshot.onrender.com/qualified_public_snapshot.json` if you use
 * `snapshot_server/` + worker POST (see README). Or override with `?api=` on the dashboard URL.
 */
window.__SNAPSHOT_URL__ =
  "https://linear-trend-spotter-snapshot.onrender.com/qualified_public_snapshot.json";

/** Operator-only relay telemetry (same host as snapshot). */
window.__RELAY_HEALTH_URL__ =
  "https://linear-trend-spotter-snapshot.onrender.com/relay-health";
