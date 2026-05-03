# Delivery mode (Telegram vs web)

This project can deliver qualified-coin **alerts and scan summaries** through **Telegram**, through the **read-only web dashboard** (and optional **Web Push**), or both. Use this page as the single reference for how that choice is configured.

**Blueprint defaults (`config.json.example` + `render.yaml` worker):** **`DELIVERY_MODE`** = **`web`**, **`TELEGRAM_ENABLED`** = **`false`**. To use Telegram again, set **`DELIVERY_MODE=telegram`**, supply bot credentials, and set **`TELEGRAM_ENABLED=true`** (see matrix below).

## Modes

| `DELIVERY_MODE` | Scanner | Telegram API (alerts) | `telegram_bot.py` listener | Dashboard / snapshot |
|-----------------|---------|-------------------------|----------------------------|------------------------|
| **`telegram`**  | Yes     | Yes, if `TELEGRAM_ENABLED` and credentials are set | Started by `run_render_worker.sh` (unless disabled below) | **Dual delivery (default):** snapshot JSON is written each scan (`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED` defaults **on**); optional relay when worker env **`QUALIFIED_SNAPSHOT_RELAY_*`** is set — **no** mode flip required. |
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

The blueprint ships **`DELIVERY_MODE=web`** / **`TELEGRAM_ENABLED=false`**. Override in the Render dashboard if you want Telegram delivery again.

## Render worker: operational matrix (environment variables only)

Use this table when tuning the **background worker** on Render. It assumes **default** app config (`PUBLIC_QUALIFIED_SNAPSHOT_ENABLED` **true** in `config/settings.py` unless you override in mounted `config.json`). **Telegram credentials** means both **`TELEGRAM_BOT_TOKEN`** and **`TELEGRAM_CHAT_ID`** are set. **Relay env** means **`QUALIFIED_SNAPSHOT_RELAY_URL`** and **`QUALIFIED_SNAPSHOT_RELAY_SECRET`** are set on the worker (snapshot **web** service also needs the **same** secret).

| Worker `DELIVERY_MODE` | Worker `TELEGRAM_ENABLED` | Entry/exit + summary **Telegram** sends | **`telegram_bot.py`** (commands) | **`qualified_public_snapshot.json`** written after scan | **Relay** `POST` after write |
|------------------------|---------------------------|----------------------------------------|----------------------------------|----------------------------------------------------------|------------------------------|
| `telegram` | `true` | Yes, if Telegram credentials present | Yes | Yes | Yes, if relay env set |
| `telegram` | `false` | No | No | Yes | Yes, if relay env set |
| `web` | `true` | **No** (`DELIVERY_MODE=web` forces Telegram off) | No | Yes | Yes, if relay env set |
| `web` | `false` | No | No | Yes | Yes, if relay env set |

**Notes (Render-only):**

- **`TELEGRAM_ENABLED`** is only consulted when **`DELIVERY_MODE`** is **`telegram`**. On **`web`**, it is **ignored** for Telegram (you can leave it `true` in the dashboard without enabling Telegram).
- **Dual delivery** = keep **`DELIVERY_MODE=telegram`**, supply Telegram secrets, and set relay env vars on the worker; the scanner sends to Telegram **and** updates the public snapshot/relay in the same run.
- To **stop** writing the snapshot file on the worker, set **`"PUBLIC_QUALIFIED_SNAPSHOT_ENABLED": false`** in **`config.json`** on the worker disk (not an env var in `settings.py` today).
- **Tier-B Web Push** (`WEB_PUSH_NOTIFY_URL`, `WEB_PUSH_INTERNAL_SECRET`, …) is independent of this matrix; see [`WEB_DASHBOARD.md`](WEB_DASHBOARD.md).

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
