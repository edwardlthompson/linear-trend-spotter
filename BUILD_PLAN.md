# Build Plan

> Bootstrap adoption and agent-ops task board. Product milestones A–Q and post-Q follow-ups (Q23+) live in `docs/EXECUTION_PLAN.md`.
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

## Sprint 7 -- Reliable notifications (Q23)

| Task | Owner | Isolated scope |
|------|-------|----------------|
| Q23a: Tier-B ops — persistent push subs, dead-sub cleanup, dashboard re-subscribe on focus | AGENT | Done — `render.yaml`, `app.js`, `WEB_DASHBOARD.md` |
| Q23b: Tier-C ntfy bridge — opt-in `NTFY_*` publish on list change | AGENT | Done — `scanner/ntfy_notify.py`, settings, docs |
| Q23c: OS-aware notification install UX (Windows/Android CTAs) | AGENT | Done — dashboard guide dialog + Settings panel, `sw.js` v102 |
| Provision ntfy topic + token on Render worker | AUTO | `scripts/provision_tier_c_ntfy.py` + snapshot `notify_public_config` |
| Privacy policy update for Tier-C external users | AGENT | Done — `docs/PRIVACY.md` |

**Order:** Q23a → Q23b → Q23c. Do not start Q23b until Q23a verification passes.

---

## Sprint 8 -- Native companions (optional, Q24–Q25)

| Task | Owner | Isolated scope |
|------|-------|----------------|
| Q24: Windows tray notifier (Python tray scaffold) | AGENT | Done — `clients/windows/` |
| Q25: Android UnifiedPush companion scaffold | ADB / AGENT | Done — `clients/android/` README + fdroid metadata |
| winget manifest validate + submit scripts | AUTO | `scripts/winget_validate.ps1`, `scripts/winget_submit.ps1` |
| winget-pkgs PR merge (Microsoft review) | HUMAN | external maintainer |
| F-Droid metadata + keystore prep script | AUTO | `scripts/android_fdroid_prepare.sh` |
| F-Droid tracker submission (after APK) | ADB | post-APK only |

---

## Ongoing Maintenance

- [ ] [HUMAN] Weekly CVE triage (recommended: Monday)
- [ ] [AGENT] Apply Dependabot bumps as needed
- [ ] [AUTO] Template update check (`scripts/check-template-updates.sh`)
