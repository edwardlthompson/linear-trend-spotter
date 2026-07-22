# Start Here

> **Read this file first** — whether you are a human or a Cursor agent.

## What is this?

**linear-trend-spotter** is a FOSS crypto exchange scanner with backtesting and a static PWA dashboard.
Agent process and tooling are aligned with [`agent-project-bootstrap`](https://github.com/edwardlthompson/agent-project-bootstrap) **v0.15.0**.
See [`docs/BOOTSTRAP_ALIGNMENT.md`](BOOTSTRAP_ALIGNMENT.md) for migration notes.

## Which repo mode are you in?

- **Bootstrap:** Not applicable — this project is already initialized (see `docs/INITIALIZATION_PROMPT.md` as reference only).
- **Reference / live product:** Read `docs/CURSOR_MODES.md`, then `docs/FOR_AGENTS.md`.

## Cursor modes (Plan / Agent / Debug / Ask)

See [`docs/CURSOR_MODES.md`](CURSOR_MODES.md) — pick the Cursor mode before editing code.

## Agent shortcuts

Type **`/`** in Cursor Agent chat for shortcut workflows. Start with [`docs/help/BATCH_COMMANDS.md`](help/BATCH_COMMANDS.md) — try `/verify` before merge or `/build` for BUILD_PLAN automation.

## Live product read order

1. `docs/START_HERE.md`
2. `docs/CURSOR_MODES.md`
3. `docs/FOR_AGENTS.md`
4. `TEMPLATE_INDEX.json`
5. `AGENTS.md`
6. `BUILD_PLAN.md` Sequential lane (ops / agent infrastructure)
7. `docs/EXECUTION_PLAN.md` for product milestones A–Q
8. Active `modules/{python,web}/MODULE.md` only
9. Golden Path app code (not `examples/`): `main.py`, `scanner/`, `backtesting/`, `docs/dashboard/`
10. `docs/WEB_PROJECT_LAYOUT.md` / `docs/DESIGN_GUIDE.md` when touching the PWA
11. `docs/FEATURE_MODULES.md` for Sprint 2+ vertical slices

## Do Not Read Yet

- Inactive `examples/` folders (not used — Golden Path is the real app)
- `KNOWLEDGE_BASE.md` unless debugging a known KB entry
- `docs/MAINTAINING_THE_TEMPLATE.md` (upstream template maintainers only)

## BUILD_PLAN Labels & status

`AGENT` | `HUMAN` | `ADB` | `AUTO` — filter with `grep '\[AGENT\]' BUILD_PLAN.md`

**Status markers on `BUILD_PLAN.md`:** 🔲 open · ✅ done · ❌ blocked (emoji only — not `- [ ]` checkboxes).

**Dual-board exception:** `docs/EXECUTION_PLAN.md` keeps GitHub `- [ ]` / `- [x]` checkboxes for product milestones. See `docs/BOOTSTRAP_ALIGNMENT.md`.

## Security

Enable Dependabot alerts on GitHub (Settings → Code security and analysis). Weekly CVE triage: `docs/SECURITY_TRIAGE.md`. Vulnerability reporting: `SECURITY.md`.

## Agent Prompts

**Live product:** Read @docs/START_HERE.md, @docs/CURSOR_MODES.md, @docs/FOR_AGENTS.md, and @TEMPLATE_INDEX.json. Use `BUILD_PLAN.md` Sequential for ops; `docs/EXECUTION_PLAN.md` for product work. Do not copy `examples/` wholesale.
