# Bootstrap Alignment — Gap Analysis & Migration Notes

> Alignment of **linear-trend-spotter** with upstream
> [`edwardlthompson/agent-project-bootstrap`](https://github.com/edwardlthompson/agent-project-bootstrap)
> **v0.15.0** (from local pin **v0.2.1**).
>
> This is a **migration on a live codebase**, not a fresh bootstrap.
> Application Golden Path code is preserved.

**Date:** 2026-07-21  
**Upstream tag:** `v0.15.0`  
**Stack:** Python worker + static Web/PWA (`modules/python`, `modules/web`)  
**Status:** Alignment pass complete (Phases 0–4). Validators green locally.

---

## Already matches (kept)

- Agent router / memory / security docs; MIT; Python + Web modules
- Product CI: `ci.yml`, `security.yml`, `codeql.yml`, `dependency-review.yml`, `health-check.yml`, `release.yml`
- Product Golden Path scripts (`ci_verify.sh`, Render helpers, backtest verifiers)
- Product board: `docs/EXECUTION_PLAN.md` (GitHub checkboxes)

## Brought in this pass

- Docs: `CURSOR_MODES.md`, batch-command docs, `DESIGN_GUIDE.md`, `WEB_PROJECT_LAYOUT.md`, `FEATURE_MODULES.md`, parallel/hygiene/Cursor integration docs, ADR stubs, this file
- Root: `.cursorignore`, `.editorconfig`, `.cursor-session-state.example.json`, `HUMAN_BACKLOG.md`, design-tokens parity, `.large-files-allowlist`
- Cursor FOSS surface: expanded `.mdc` rules, `.cursor/commands/`, agents, skills, hooks, `stack-selection.json`, worktrees, permissions
- Scripts: hygiene / gates / parallel / batch / feature-gate family + `scripts/lib/` (merged; product scripts preserved)
- CI: OpenSSF `scorecard.yml` only
- Adapted `validate-bootstrap.sh` (upstream REQUIRED + `uv.lock` + `EXECUTION_PLAN.md`)

## Conflicts and handling

| Conflict | Handling |
|----------|----------|
| `BUILD_PLAN.md` used `- [ ]` + tables | Migrated to emoji `🔲/✅/❌` + Sequential / Parallel / Human lanes |
| `docs/EXECUTION_PLAN.md` mandates GitHub checkboxes | **Kept** — dual-board exception |
| Line limits 250 vs upstream 300 | **Keep 250 view / 150 logic** |
| Large tracked PWA icons / `uv.lock` | Allowlisted in `.large-files-allowlist` |
| `LICENSE` was UTF-16 LE | Re-encoded UTF-8 without BOM |
| release-please | Manifest only for version sync — **no** release-please workflows |

## Stack selection

- `distribution_tier`: foss
- `stack`: multi (python + web)
- Golden Path = real app — not `examples/`

## Chosen defaults (executed)

- **CI:** Keep existing six workflows; add Scorecard only
- **Hooks:** FOSS Cursor surface enabled (`hooks.json`)
- **Status markers:** Emoji on `BUILD_PLAN.md` only
- **Target pin:** `0.15.0` (includes 0.14.x surface + latest template tag)

---

## Migration notes (for humans)

### What changed

1. Agent entrypoints: START_HERE → CURSOR_MODES → FOR_AGENTS / BUILD_PLAN (live product Reference mode).
2. Batch commands (`/`), expanded rules, hooks, skills, subagents, worktrees.
3. `BUILD_PLAN.md` rebuilt with official labels and emoji status markers.
4. Bootstrap validation expanded; product scripts and Golden Path unchanged.
5. OpenSSF Scorecard workflow added; release-please / automerge / stale / pages **not** adopted.
6. `.template-version` / `TEMPLATE_INDEX.json` / `.release-please-manifest.json` synced to **0.15.0**.
7. `bash scripts/validate-bootstrap.sh` passed after alignment.

### What still needs manual attention (`[HUMAN]` / `[ADB]`)

- Enable **Private vulnerability reporting** (GitHub Settings → Code security; UI-only).
- Confirm Scorecard workflow permissions / optional README badge.
- Weekly CVE triage (`docs/SECURITY_TRIAGE.md`).
- winget-pkgs PR merge (external); F-Droid submission after APK (`[ADB]`).
- Optional later: release-please, Dependabot automerge, stale, pages; dashboard ↔ design-token sync; EXECUTION_PLAN emoji migration.
- **Commit:** agent left a dirty tree unless you ask for a Conventional Commit.

### Dual-board convention

| Board | Status format | Use for |
|-------|---------------|---------|
| `BUILD_PLAN.md` | `🔲` / `✅` / `❌` | Bootstrap, ops, agent infrastructure |
| `docs/EXECUTION_PLAN.md` | `- [ ]` / `- [x]` | Product milestones A–Q and post-Q follow-ups |

---

## Validation

```bash
bash scripts/validate-bootstrap.sh
bash scripts/validate-template-index.sh
bash scripts/check-file-encoding.sh
bash scripts/check-batch-commands.sh
bash scripts/check-repo-hygiene.sh
```
