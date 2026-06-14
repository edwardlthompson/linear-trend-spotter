/** Same as committed `config.js`: default is same-origin JSON on GitHub Pages (`../qualified_public_snapshot.json`). */
window.__SNAPSHOT_URL__ = "../qualified_public_snapshot.json";

/** Optional: snapshot relay operator JSON (default = same directory as __SNAPSHOT_URL__ + `relay-health`). */
// window.__RELAY_HEALTH_URL__ = "https://YOUR-SNAPSHOT-SERVICE.onrender.com/relay-health";

/** Optional Tier-B Web Push: relay base (no trailing slash), VAPID public key, optional subscribe token. Worker notifies on qualified-list entry/exit only. */
// window.__PUSH_API_BASE__ = "https://YOUR-PUSH-SERVICE.onrender.com";
// window.__VAPID_PUBLIC_KEY__ = "BN…"; /* from `npx web-push generate-vapid-keys` or equivalent */
// window.__PUSH_SUBSCRIBE_TOKEN__ = ""; /* if WEB_PUSH_SUBSCRIBE_TOKEN is set on the push service */

/** Optional Tier-C ntfy: public subscribe URL for dashboard install hints (unguessable topic; use auth token on server). */
// window.__NTFY_SUBSCRIBE_URL__ = "https://ntfy.sh/your-secret-topic";
// window.__NTFY_ANDROID_APP_URL__ = "https://f-droid.org/packages/io.heckel.ntfy/";
// window.__NTFY_DESKTOP_URL__ = "https://ntfy.sh/app";
// window.__WINDOWS_TRAY_RELEASE_URL__ = "https://github.com/edwardlthompson/linear-trend-spotter/releases/latest";
