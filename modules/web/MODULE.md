# Module B: Web / Static Sites / Progressive Web Apps (PWAs)

> Active for Linear Trend Spotter static dashboard at `docs/dashboard/`.

## Requirements (Verbatim)

- **PWA & Cache Integrity:** Enforce fully compliant PWA manifests, offline-first service workers, and responsive offline caching.
- **Asset Optimization & Audits:** Lighthouse CI deferred to BUILD_PLAN Sprint 6.

## Activation Checklist

- [x] Add `manifest.webmanifest` with required fields
- [x] Implement offline-first service worker (`docs/dashboard/sw.js`)
- [ ] Configure Lighthouse CI budgets (Sprint 6)
- [ ] Set up axe-core accessibility tests in Playwright (Sprint 6)
- [x] Golden Path: `docs/dashboard/` (not `examples/web/`)
- [ ] Add visual regression snapshots for key pages
- [ ] Enforce bundle size budgets in CI
- [ ] Keyboard-only navigation smoke test checklist
- [x] Respect `prefers-reduced-motion` and `prefers-color-scheme` (theme toggle)
- [ ] i18n extraction workflow if multi-locale

## Operations (when deployed as service)

- [x] Static hosting via GitHub Pages; live JSON via snapshot relay
- [ ] Structured logging standard per `docs/RUNBOOK.md`

## Golden Path Reference

See [docs/dashboard/](../docs/dashboard/) and [docs/WEB_DASHBOARD.md](../docs/WEB_DASHBOARD.md).

## Owner Labels for This Module

| Task type | Label |
|-----------|-------|
| Scaffold PWA, tests, CI config | `AGENT` |
| Lighthouse budget threshold approval | `HUMAN` |
| CI Lighthouse/axe gate enforcement | `AUTO` |
