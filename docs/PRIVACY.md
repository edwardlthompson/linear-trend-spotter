# Privacy

> Privacy policy draft for Linear Trend Spotter. Not legal advice.

## Summary

Linear Trend Spotter does **not** operate user accounts. The scanner runs as a background worker; the dashboard is a static PWA that fetches public JSON. Optional Web Push requires explicit browser consent.

## Data Collected

| Data | Where | Purpose | Retention |
|------|-------|---------|-----------|
| Qualified coin market data | Public snapshot JSON | Dashboard display | Until next scan overwrites |
| Watchlist pins | Browser `localStorage` only | Client UX | Until user clears site data |
| Theme preference | Browser `localStorage` | Client UX | Until user clears site data |
| Push subscription endpoint | push_server file (if Tier-B enabled) | Deliver list-change notifications | Until unsubscribe or redeploy |
| ntfy topic messages | ntfy.sh or self-hosted ntfy (if Tier-C enabled) | Deliver list-change notifications to subscribed clients | Operator / ntfy retention policy |
| Scan logs / SQLite | Render disk | Operations, caching | Operator-controlled |

## Data Not Collected

- No analytics telemetry by default (opt-in only if added later)
- No user email, name, or authentication
- No tracking cookies on the static dashboard

## Third Parties

- **Exchange / market data APIs** — worker calls configured providers (CoinGecko, CMC, Polygon, etc.)
- **Render** — hosts worker and optional relays
- **GitHub Pages** — hosts static dashboard assets

## User Controls

- Clear site data in browser to remove watchlist/theme
- Unsubscribe from Web Push via browser notification settings
- Do not enable push_server if notifications are not desired
- **Tier-C ntfy:** unsubscribe or delete the topic in the ntfy app; Tier-C is opt-in on the operator side (`NTFY_ENABLED` defaults off)
- **Tier-C ntfy:** do not subscribe to operator topics you do not trust; topic URLs should be treated as capability URLs

## GDPR / CCPA Notes

- No personal data processed by the worker in default configuration
- Push subscriptions contain browser-generated endpoints (pseudonymous)
- Operators deploying their own instance are data controllers for their deployment

## DPIA Checklist (operator)

- [ ] Document which API keys and env vars are set on Render
- [ ] Confirm snapshot JSON contains no secrets before public GET
- [ ] Review CORS origins on snapshot and push relays
- [ ] Confirm push subscribe token policy if exposed publicly
