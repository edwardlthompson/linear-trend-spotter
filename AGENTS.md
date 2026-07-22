# Agent Router

1. **First read:** `docs/START_HERE.md`
2. **Cursor modes:** `docs/CURSOR_MODES.md` (Ask / Plan / Agent / Debug routing)
3. **Bootstrap mode:** `docs/INITIALIZATION_PROMPT.md` (reference-only — project already initialized)
4. **Reference mode:** `docs/FOR_AGENTS.md` + `TEMPLATE_INDEX.json`
5. **Task boards:** `BUILD_PLAN.md` for bootstrap/ops (Sequential before Parallel; status 🔲/✅/❌); `docs/EXECUTION_PLAN.md` for product milestones A–Q (`- [ ]` / `- [x]`)
6. **Parallel dispatch:** isolated scopes via `docs/PARALLEL_AGENT_SCOPES.md`; `/build` attempts HUMAN/ADB after automation and logs failures to `HUMAN_BACKLOG.md`
7. **Living memory:** update `AGENT_MEMORY.md` only at milestone boundaries
8. **Alignment notes:** `docs/BOOTSTRAP_ALIGNMENT.md`

> Legacy `.cursorrules` is deprecated. Use `.cursor/rules/*.mdc` and this file instead.

## Architecture Constraints

- Pure FOSS under MIT license; no proprietary closed-source SDKs in production path
- Max **250** lines per view file, **150** lines per logic file (legacy files exempt until refactor sprint) — project override vs upstream 300/150
- Strict type safety and runtime validation at all data boundaries
- Core business logic decoupled from layout framework (MVVM / Clean / Hexagonal)
- Opt-in only telemetry; GDPR/CCPA compliant

## Coding Style

- Conventional Commits for all changes
- Small, modular functions; keep files within token-optimal size
- Read-before-write: inspect types/interfaces via `@filename` before editing
- Cursor mode routing per `docs/CURSOR_MODES.md`; Plan for non-trivial tasks with `### Critique`

## Session Protocol

- On session start: read `START_HERE.md`, pick mode via `CURSOR_MODES.md`, then `BUILD_PLAN.md` Sequential (or `EXECUTION_PLAN.md` for product work)
- On milestone end: update `AGENT_MEMORY.md`, append to `DECISION_LOG.md` or `docs/adr/`
- On 3-strike failure: halt and escalate to human
- On context bloat: write `.cursor-session-state`, ask human to clear chat
- After Sprint 2+ AGENT steps: run `scripts/watch-agent-gates.sh --once --autofix` when available
- Destructive operations require `[HUMAN]` approval (see `.cursor/rules/destructive-ops.mdc`)
- Repo hygiene: run `scripts/check-repo-hygiene.sh` before push when available
- Log significant agent actions in `DECISION_LOG.md` at milestone boundaries

## Module Activation

Active modules: **Python** (`modules/python/MODULE.md`) and **Web/PWA** (`modules/web/MODULE.md`).

Golden Path is the real application — not `examples/`:

- Python worker: `main.py`, `scanner/`, `backtesting/`
- Static PWA: `docs/dashboard/`
- Microservices: `push_server/`, `snapshot_server/`

## Cursor FOSS integrations

See `docs/CURSOR_INTEGRATIONS.md`:

- **Hooks** — `.cursor/hooks.json` (destructive-ops + UTF-8; fail-open)
- **Skills** — `.cursor/skills/`
- **Subagents** — `.cursor/agents/` (verifier, gate-fixer, explorer)
- **Local compute first** — `.cursor/rules/local-compute.mdc`
- **Worktrees** — `.cursor/worktrees.json`
- **Permissions** — `.cursor/permissions.json`
- **Optional MCP** — copy `.cursor/mcp.foss.example` → gitignored `.cursor/mcp.json`

## Ecosystem-Specific Rules

- **Web/PWA:** Offline-first service worker in `docs/dashboard/sw.js`; Lighthouse CI deferred (BUILD_PLAN)
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
