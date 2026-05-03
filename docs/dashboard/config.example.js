/** Same as committed `config.js`: default is same-origin JSON on GitHub Pages (`../qualified_public_snapshot.json`). */
window.__SNAPSHOT_URL__ = "../qualified_public_snapshot.json";

/** Optional: snapshot relay operator JSON (default = same directory as __SNAPSHOT_URL__ + `relay-health`). */
// window.__RELAY_HEALTH_URL__ = "https://YOUR-SNAPSHOT-SERVICE.onrender.com/relay-health";

/** Optional Tier-B Web Push (Q21): public relay base (no trailing slash), VAPID public key, optional subscribe token. */
// window.__PUSH_API_BASE__ = "https://YOUR-PUSH-SERVICE.onrender.com";
// window.__VAPID_PUBLIC_KEY__ = "BN…"; /* from `npx web-push generate-vapid-keys` or equivalent */
// window.__PUSH_SUBSCRIBE_TOKEN__ = ""; /* if WEB_PUSH_SUBSCRIBE_TOKEN is set on the push service */
