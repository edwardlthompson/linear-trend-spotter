# Release notes

Short summaries of operator-facing changes. Engineering milestones remain in [`EXECUTION_PLAN.md`](EXECUTION_PLAN.md).

## 2026-05-01 — Web-first delivery (trial)

**Delivery defaults are now web/dashboard–centric** rather than Telegram-first:

- **`config/settings.py`** defaults: **`DELIVERY_MODE`** = **`web`**, **`TELEGRAM_ENABLED`** = **`false`**.
- **`config.json.example`** matches that shape and sets **`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`** = **`true`** so new deployments publish the qualified snapshot for the static dashboard (still configure the snapshot relay URL on the worker if you use GitHub Pages).
- **`render.yaml`** worker env: **`DELIVERY_MODE=web`**, **`TELEGRAM_ENABLED=false`** — the bundled worker script **does not** start **`telegram_bot.py`**.

**README** describes this layout as the current norm; Telegram remains optional via [`DELIVERY_MODE.md`](DELIVERY_MODE.md).

To revert to Telegram delivery for a host, set **`DELIVERY_MODE`** to **`telegram`**, **`TELEGRAM_ENABLED`** to **`true`**, supply **`TELEGRAM_BOT_TOKEN`** / **`TELEGRAM_CHAT_ID`**, and redeploy.
