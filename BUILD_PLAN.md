# Build Plan

> Bootstrap adoption and agent-ops task board. Product milestones A-Q live in `docs/EXECUTION_PLAN.md`.
> Finished items are archived in `COMPLETED_TASKS.md`.

## Owner Label Legend

| Label | Owner | When to use |
|-------|-------|-------------|
| `AGENT` | Cursor Agent | Code, docs, scaffolding, tests, CI config |
| `HUMAN` | Human developer | Approvals, credentials, GitHub settings, product decisions |
| `ADB` | Human (Android) | Not applicable to this project |
| `AUTO` | CI/scripts/bots | GitHub Actions, Dependabot, pre-commit, update checker |

---

## Remaining one-time setup

1. [ ] [HUMAN] Enable **Private vulnerability reporting** in GitHub Settings -> Code security (API returns 404; UI-only on this repo)

---

## Sprint 5 -- Security and Ops (recurring)

- [ ] [HUMAN] Weekly CVE triage (recommended: Monday) -- see `docs/SECURITY_TRIAGE.md`
- [ ] [AGENT] Apply Dependabot bumps as needed
- [ ] [AUTO] Trivy + CodeQL + CI green after merges (`health-check.yml` weekly)

---

## Sprint 6 -- Web Module (Deferred)

| Task | Owner | Isolated scope |
|------|-------|----------------|
| Backtest Results modal: show TSL % + TSL hit % columns (Q22) | AGENT | Done — `docs/dashboard/app.js`, `sw.js` v100 |
| Lighthouse CI for `docs/dashboard/` | AGENT | npm tooling under dashboard |
| axe-core accessibility tests | AGENT | `docs/dashboard/` |
| File line-limit refactor | HUMAN decision | large legacy modules |

---

## Ongoing Maintenance

- [ ] [HUMAN] Weekly CVE triage (recommended: Monday)
- [ ] [AGENT] Apply Dependabot bumps as needed
- [ ] [AUTO] Template update check (`scripts/check-template-updates.sh`)
