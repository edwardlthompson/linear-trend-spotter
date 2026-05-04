# Delivery (web)

Alerts and the qualified list are **not** sent to third-party chat apps. After each scan the worker writes **`qualified_public_snapshot.json`**, can **POST** it to your **`snapshot_server`** relay for the dashboard, and optionally notifies a **web push** relay when the active list changes. See **`docs/WEB_DASHBOARD.md`** and the main **README** for environment variables and hosting.
