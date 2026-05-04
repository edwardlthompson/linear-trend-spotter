# Release notes

Operator-facing summaries. Engineering milestones remain in [`EXECUTION_PLAN.md`](EXECUTION_PLAN.md).

## 2026-05-03 — Web-only delivery

- **Removed** the Telegram bot client, long-running **`telegram_bot.py`**, **`manage_bot.py`**, and related settings/env vars. Alerts are **dashboard + optional snapshot relay + optional Tier-B web push** only—see [`DELIVERY_MODE.md`](DELIVERY_MODE.md) and [`WEB_DASHBOARD.md`](WEB_DASHBOARD.md).
- **`render.yaml`**: dropped **`DELIVERY_MODE`**, **`TELEGRAM_ENABLED`**, **`TELEGRAM_BOT_TOKEN`**, **`TELEGRAM_CHAT_ID`** from the worker blueprint (defaults are now implicit web delivery in code).

Older dated entries below are **historical**; they may mention Telegram options that no longer exist in the codebase.

---

## 2026-05-02 — (historical) Telegram-first defaults trial

Superseded by web-first and then web-only releases above.

## 2026-05-01 — (historical) Web-first delivery trial

Superseded; snapshot + dashboard path remains the supported model.
