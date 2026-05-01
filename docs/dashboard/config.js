/**
 * Public snapshot JSON (HTTPS). Not a secret — browsers fetch this URL.
 *
 * Replace YOUR-SERVICE with your Render web service hostname (no trailing slash on host).
 * Example: https://linear-trend-spotter-worker.onrender.com/qualified_public_snapshot.json
 *
 * Or omit this file’s assignment and open the dashboard with:
 *   ?api=https%3A%2F%2FYOUR-SERVICE.onrender.com%2Fqualified_public_snapshot.json
 *
 * Ensure Render (or your host) sends CORS allowing https://edwardlthompson.github.io for GET on this file.
 */
window.__SNAPSHOT_URL__ = "https://YOUR-SERVICE.onrender.com/qualified_public_snapshot.json";
