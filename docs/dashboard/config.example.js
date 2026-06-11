/** Public snapshot JSON. Use the live relay in production; same-origin JSON also works for local/static-only preview. */
window.__SNAPSHOT_URL__ = "https://YOUR-SNAPSHOT-SERVICE.onrender.com/qualified_public_snapshot.json";

/** Optional: snapshot relay operator JSON (default = same directory as __SNAPSHOT_URL__ + `relay-health`). */
// window.__RELAY_HEALTH_URL__ = "https://YOUR-SNAPSHOT-SERVICE.onrender.com/relay-health";

/** Optional Tier-B Web Push: relay base (no trailing slash), VAPID public key, optional subscribe token. Worker notifies on qualified-list entry/exit only. */
// window.__PUSH_API_BASE__ = "https://YOUR-PUSH-SERVICE.onrender.com";
// window.__VAPID_PUBLIC_KEY__ = "BN…"; /* from `npx web-push generate-vapid-keys` or equivalent */
// window.__PUSH_SUBSCRIBE_TOKEN__ = ""; /* if WEB_PUSH_SUBSCRIBE_TOKEN is set on the push service */
