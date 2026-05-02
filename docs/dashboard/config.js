/**
 * Public snapshot JSON (HTTPS). Not a secret — browsers fetch this URL.
 *
 * Use the snapshot **relay** web service (`snapshot_server/` in repo, `linear-trend-spotter-snapshot`
 * in render.yaml), not the worker — Render background workers do not serve HTTP files.
 *
 * Example: https://linear-trend-spotter-snapshot.onrender.com/qualified_public_snapshot.json
 *
 * Or omit this file’s assignment and open the dashboard with:
 *   ?api=https%3A%2F%2Fyour-snapshot-service.onrender.com%2Fqualified_public_snapshot.json
 *
 * Set worker env QUALIFIED_SNAPSHOT_RELAY_URL + QUALIFIED_SNAPSHOT_RELAY_SECRET so each scan POSTs JSON to the relay.
 */
window.__SNAPSHOT_URL__ =
  "https://YOUR-SNAPSHOT-SERVICE.onrender.com/qualified_public_snapshot.json";
