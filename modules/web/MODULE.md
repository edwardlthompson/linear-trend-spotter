# Module B: Web / Static Sites / Progressive Web Apps (PWAs)

> Active for Linear Trend Spotter static dashboard at `docs/dashboard/`.
> Layout notes: [`docs/WEB_PROJECT_LAYOUT.md`](../../docs/WEB_PROJECT_LAYOUT.md).

## Requirements (Verbatim)

- **PWA & Cache Integrity:** Enforce fully compliant PWA manifests, offline-first service workers, and responsive offline caching.
- **Asset Optimization & Audits:** Lighthouse CI deferred to BUILD_PLAN Sprint 6.

## Activation Checklist

- ✅ [AGENT] Add `manifest.webmanifest` with required fields
- ✅ [AGENT] Implement offline-first service worker (`docs/dashboard/sw.js`)
- 🔲 [AGENT] Configure Lighthouse CI budgets (Sprint 6)
- 🔲 [AGENT] Set up axe-core accessibility tests (Sprint 6)
- ✅ [AGENT] Golden Path: `docs/dashboard/` (not `examples/web/`)
- 🔲 [AGENT] Add visual regression snapshots for key pages
- 🔲 [AGENT] Enforce bundle size budgets in CI
- 🔲 [AGENT] Keyboard-only navigation smoke test checklist
- ✅ [AGENT] Respect `prefers-reduced-motion` and `prefers-color-scheme` (theme toggle)
- 🔲 [AGENT] i18n extraction workflow if multi-locale
- 🔲 [AGENT] Sync `design-tokens/` into `docs/dashboard/styles.css` (dashboard CSS is source of truth today)

## Operations (when deployed as service)

- ✅ [AUTO] Static hosting via GitHub Pages; live JSON via snapshot relay
- 🔲 [AGENT] Structured logging standard per `docs/RUNBOOK.md`

## Golden Path Reference

See [docs/dashboard/](../../docs/dashboard/) and [docs/WEB_DASHBOARD.md](../../docs/WEB_DASHBOARD.md).

## Owner Labels for This Module

| Task type | Label |
|-----------|-------|
| Scaffold PWA, tests, CI config | `AGENT` |
| Lighthouse budget threshold approval | `HUMAN` |
| CI Lighthouse/axe gate enforcement | `AUTO` |
