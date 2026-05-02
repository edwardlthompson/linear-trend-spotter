# Delivery mode (Telegram vs web)

This project can deliver qualified-coin **alerts and scan summaries** through **Telegram**, through the **read-only web dashboard** (and optional **Web Push**), or both. Use this page as the single reference for how that choice is configured.

**Repository defaults (as of 2026-05):** **`DELIVERY_MODE`** = **`web`**, **`TELEGRAM_ENABLED`** = **`false`** — see [`RELEASE_NOTES.md`](RELEASE_NOTES.md).

## Modes

| `DELIVERY_MODE` | Scanner | Telegram API (alerts) | `telegram_bot.py` listener | Dashboard / snapshot |
|-----------------|---------|-------------------------|----------------------------|------------------------|
| **`telegram`**  | Yes     | Yes, if `TELEGRAM_ENABLED` and credentials are set | Started by `run_render_worker.sh` (unless disabled below) | Optional: enable snapshot + relay for the website |
| **`web`**       | Yes     | No (client not created) | Not started | Primary: public JSON + `docs/dashboard/`; optional Tier-B Web Push |

## Precedence (effective Telegram on/off)

1. **`DELIVERY_MODE`**  
   - Config: `config.json` → `"DELIVERY_MODE": "web"` or `"telegram"`.  
   - Environment: **`DELIVERY_MODE=web`** or **`DELIVERY_MODE=telegram`** overrides config when set (Render-friendly).

2. **`TELEGRAM_ENABLED`** (only meaningful when `DELIVERY_MODE` is **`telegram`**)  
   - Config default: `true`.  
   - Environment **`TELEGRAM_ENABLED`** overrides with truthy/falsey strings (`false`, `0`, `true`, `1`, …).

**Net effect:** If `DELIVERY_MODE` is **`web`**, Telegram delivery is **off** regardless of tokens or `TELEGRAM_ENABLED`. To disable Telegram while keeping `DELIVERY_MODE=telegram`, set **`TELEGRAM_ENABLED`** to **`false`** (and/or remove **`TELEGRAM_BOT_TOKEN`** / **`TELEGRAM_CHAT_ID`**).

## Worker process on Render

`scripts/run_render_worker.sh` starts **`telegram_bot.py`** in the background **only** when:

- `DELIVERY_MODE` is **not** `web`, and  
- `TELEGRAM_ENABLED` is **not** `false` / `0`.

Set **`DELIVERY_MODE=web`** (and optionally **`TELEGRAM_ENABLED=false`**) in the worker service environment. The blueprint in `render.yaml` includes **`DELIVERY_MODE`** / **`TELEGRAM_ENABLED`** defaults you can override in the dashboard.

## Web-only checklist

1. **`DELIVERY_MODE`:** `"web"` in `config.json` and/or **`DELIVERY_MODE=web`** on the host.  
2. **Snapshot:** `PUBLIC_QUALIFIED_SNAPSHOT_ENABLED`, relay **`QUALIFIED_SNAPSHOT_RELAY_*`** if using GitHub Pages (see root `README.md`).  
3. **Dashboard:** `docs/dashboard/` URL + optional Tier-A/Tier-B alerts (`docs/WEB_DASHBOARD.md`).  
4. **Secrets:** You may omit Telegram secrets when nothing uses Telegram; they are ignored for delivery when the effective mode is web-only.

## Local tools

- **`manage_bot.py`** refuses to start the bot when Telegram is effectively disabled.  
- **`telegram_bot.py`** run directly exits with a short message when Telegram is disabled.

## See also

- [`README.md`](../README.md) — “Operating without Telegram”  
- [`WEB_DASHBOARD.md`](WEB_DASHBOARD.md) — dashboard, CORS, Web Push
