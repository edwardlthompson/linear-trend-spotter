# Agent Router

1. **First read:** `docs/START_HERE.md`
2. **Bootstrap mode:** `docs/INITIALIZATION_PROMPT.md` (reference-only — project already initialized)
3. **Reference mode:** `docs/FOR_AGENTS.md` + `TEMPLATE_INDEX.json`
4. **Task board:** `BUILD_PLAN.md` for bootstrap/ops; `docs/EXECUTION_PLAN.md` for product milestones A–Q
5. **Living memory:** update `AGENT_MEMORY.md` only at milestone boundaries

> Legacy `.cursorrules` is deprecated. Use `.cursor/rules/*.mdc` and this file instead.

## Architecture Constraints

- Pure FOSS under MIT license; no proprietary closed-source SDKs in production path
- Max 250 lines per view file, 150 lines per logic file (legacy files exempt until refactor sprint)
- Strict type safety and runtime validation at all data boundaries
- Core business logic decoupled from layout framework (MVVM / Clean / Hexagonal)
- Opt-in only telemetry; GDPR/CCPA compliant

## Coding Style

- Conventional Commits for all changes
- Small, modular functions; keep files within token-optimal size
- Read-before-write: inspect types/interfaces via `@filename` before editing
- Plan Mode for all non-trivial tasks; include `### Critique` in plans

## Session Protocol

- On session start: read `START_HERE.md`, then `BUILD_PLAN.md` Sequential lane (or `EXECUTION_PLAN.md` for product work)
- On milestone end: update `AGENT_MEMORY.md`, append to `DECISION_LOG.md` or `docs/adr/`
- On 3-strike failure: halt and escalate to human
- On context bloat: write `.cursor-session-state`, ask human to clear chat
- Destructive operations require `[HUMAN]` approval (see `.cursor/rules/destructive-ops.mdc`)
- Log significant agent actions in `DECISION_LOG.md` at milestone boundaries

## Module Activation

Active modules: **Python** (`modules/python/MODULE.md`) and **Web/PWA** (`modules/web/MODULE.md`).

Golden Path is the real application — not `examples/`:

- Python worker: `main.py`, `scanner/`, `backtesting/`
- Static PWA: `docs/dashboard/`
- Microservices: `push_server/`, `snapshot_server/`

## Ecosystem-Specific Rules

- **Web/PWA:** Offline-first service worker in `docs/dashboard/sw.js`; Lighthouse CI deferred to BUILD_PLAN Sprint 3+
- **Python:** Strict typing (mypy), ruff lint, locked dependencies via `uv.lock`
- **Deploy:** Render worker build must stay parity with `scripts/ci_verify.sh`

## Project-Specific Constraints

You MUST exercise independent reasoning while working on this project.

If existing code, methods, schemas, or processes are inefficient or logically flawed, you MUST:

1. Identify the issue clearly.
2. Proactively generate improvements.
3. Explicitly state when and why you are deviating from prior logic.

Additional rules:

- Do NOT replicate inefficient logic during refactoring, porting, or planning.
- Challenge assumptions and surface architectural weaknesses when detected.
- Improvements should be proportional to the scope of the change.
- Avoid unnecessary architectural expansion.
- Always save files using UTF-8 encoding without BOM.
- When authoring sprint plans, sequence development sessions in chronological order.
- Follow **Non-regression & scope guardrails** in `docs/EXECUTION_PLAN.md` for all product milestone work.
- Do not reduce scan universe, change scan interval, or alter OHLCV provider order without explicit product approval.
- Keep GitHub CI green (`CI`, `Security Scan`, `CodeQL`) before marking EXECUTION_PLAN milestones complete.
