/** Same as committed `config.js`: public snapshot URL (or use `?api=` on the dashboard URL). Use the snapshot relay web service, not the worker. */
window.__SNAPSHOT_URL__ =
  "https://YOUR-SNAPSHOT-SERVICE.onrender.com/qualified_public_snapshot.json";

/** Optional Tier-B Web Push (Q21): public relay base (no trailing slash), VAPID public key, optional subscribe token. */
// window.__PUSH_API_BASE__ = "https://YOUR-PUSH-SERVICE.onrender.com";
// window.__VAPID_PUBLIC_KEY__ = "BN…"; /* from `npx web-push generate-vapid-keys` or equivalent */
// window.__PUSH_SUBSCRIBE_TOKEN__ = ""; /* if WEB_PUSH_SUBSCRIBE_TOKEN is set on the push service */
