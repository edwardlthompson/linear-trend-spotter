# Build Plan

> Bootstrap adoption and agent-ops task board. Product milestones A–Q and post-Q follow-ups live in `docs/EXECUTION_PLAN.md`.
> Finished items are archived in `COMPLETED_TASKS.md`. Alignment details: `docs/BOOTSTRAP_ALIGNMENT.md`.

## Owner Label Legend

| Label | Owner | When to use |
|-------|-------|-------------|
| `AGENT` | Cursor Agent | Code, docs, scaffolding, tests, CI config |
| `HUMAN` | Human developer | Approvals, credentials, GitHub settings, product decisions |
| `ADB` | Human (Android) | Device/F-Droid items (limited applicability here) |
| `AUTO` | CI/scripts/bots | GitHub Actions, Dependabot, pre-commit, update checker |

## Status markers

Use **emoji markers** (not `- [ ]` GitHub checkboxes) so task state reads clearly in Markdown source and Preview.

| Marker | Meaning | Notes |
|--------|---------|-------|
| 🔲 | Open | Default for new tasks |
| ✅ | Done | Replace 🔲 when complete; archive sprint rows to `COMPLETED_TASKS.md` |
| ❌ | Blocked | Add brief reason after the description |

**Task format:** `🔲 [OWNER] Description` · done: `✅ [OWNER] Description` · blocked: `❌ [OWNER] Description — reason`

**Dual-board exception:** `docs/EXECUTION_PLAN.md` keeps `- [ ]` / `- [x]` for product milestones.

**Agent rule:** Execute all `[AGENT]` **Sequential** items first, then dispatch **Parallel** agents with isolated file scopes (`docs/PARALLEL_AGENT_SCOPES.md`). Shared schema/types are Sequential-only.

---

## Sprint A15 — Bootstrap alignment v0.15.0

> Align child repo with upstream `agent-project-bootstrap` v0.15.0 without rewriting Golden Path application code.

### Sequential

- ✅ [AGENT] Write `docs/BOOTSTRAP_ALIGNMENT.md` gap analysis + DECISION_LOG entry
- ✅ [AGENT] Refresh START_HERE / CURSOR_MODES / FOR_AGENTS / AGENTS.md for live product (v0.15.0)
- ✅ [AGENT] Add batch-command docs, `.cursor/commands/`, expanded `.cursor/rules/` (incl. local-compute)
- ✅ [AGENT] Ship FOSS Cursor surface (hooks, skills, agents, stack-selection, worktrees)
- ✅ [AGENT] Rebuild BUILD_PLAN with emoji markers + lanes
- ✅ [AGENT] Merge upstream scripts + adapted `validate-bootstrap.sh`; add Scorecard workflow
- ✅ [AGENT] Refresh modules + WEB_PROJECT_LAYOUT / DESIGN_GUIDE / design-tokens note
- ✅ [AGENT] Update TEMPLATE_INDEX; run validators; bump `.template-version` to 0.15.0

### Parallel

<!-- parallel_exception: A15 alignment is single-agent Sequential (shared docs/scripts schema) -->

### Human & device (after automation)

- 🔲 [HUMAN] Enable Private vulnerability reporting (GitHub Settings → Code security)
- 🔲 [HUMAN] Confirm OpenSSF Scorecard workflow permissions / optional badge
- 🔲 [HUMAN] Weekly CVE triage (recommended: Monday) — `docs/SECURITY_TRIAGE.md`

---

## Sprint 5 — Security and Ops (recurring)

### Sequential

- 🔲 [AGENT] Apply Dependabot bumps as needed
- 🔲 [AUTO] Trivy + CodeQL + CI green after merges (`health-check.yml` weekly)
- 🔲 [AUTO] Template update check (`scripts/check-template-updates.sh`)

### Parallel

<!-- parallel_exception: recurring ops — no parallel table this cycle -->

### Human & device (after automation)

- 🔲 [HUMAN] Weekly CVE triage (recommended: Monday) — see `docs/SECURITY_TRIAGE.md`

---

## Sprint 6 — Web Module (deferred items)

### Sequential

- ✅ [AGENT] Backtest Results modal: TSL % + TSL hit % columns (Q22) — `docs/dashboard/app.js`, `sw.js`
- 🔲 [AGENT] Lighthouse CI for `docs/dashboard/`
- 🔲 [AGENT] axe-core accessibility tests for `docs/dashboard/`
- 🔲 [HUMAN] File line-limit refactor decision for large legacy modules

### Parallel

<!-- parallel_exception: Sprint 6 deferred web a11y/Lighthouse share docs/dashboard — run Sequential when unblocked -->

---

## Sprint 7 — Reliable notifications (Q23)

### Sequential

- ✅ [AGENT] Q23a Tier-B ops — persistent push subs, dead-sub cleanup, re-subscribe on focus
- ✅ [AGENT] Q23b Tier-C ntfy bridge — opt-in `NTFY_*` publish on list change
- ✅ [AGENT] Q23c OS-aware notification install UX
- ✅ [AUTO] Provision ntfy topic + token helper — `scripts/provision_tier_c_ntfy.py`
- ✅ [AGENT] Privacy policy update for Tier-C — `docs/PRIVACY.md`

### Parallel

<!-- parallel_exception: Q23 complete -->

### Human & device (after automation)

_(none open)_

---

## Sprint 8 — Native companions (optional, Q24–Q25)

### Sequential

- ✅ [AGENT] Q24 Windows tray notifier scaffold — `clients/windows/`
- ✅ [AGENT] Q25 Android UnifiedPush companion scaffold — `clients/android/`
- ✅ [AUTO] winget validate/submit scripts — `scripts/winget_*.ps1`
- ✅ [AUTO] F-Droid metadata + keystore prep — `scripts/android_fdroid_prepare.sh`

### Parallel

<!-- parallel_exception: scaffolds complete -->

### Human & device (after automation)

- 🔲 [HUMAN] winget-pkgs PR merge (Microsoft review)
- 🔲 [ADB] F-Droid tracker submission (after APK)

---

## Ongoing Maintenance

### Sequential

- 🔲 [AGENT] Apply Dependabot bumps as needed
- 🔲 [AUTO] Template update check (`scripts/check-template-updates.sh`)

### Human & device (after automation)

- 🔲 [HUMAN] Weekly CVE triage (recommended: Monday)
