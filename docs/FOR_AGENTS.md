# For Agents

## Phased Loading

SessionStart → `START_HERE.md` → `CURSOR_MODES.md` → Mode → `AGENTS.md` → `BUILD_PLAN` Sequential → Active module → Golden Path → Plan Mode → Execute

For **product** milestones use `docs/EXECUTION_PLAN.md` (GitHub checkboxes) instead of or in addition to `BUILD_PLAN.md`.

## Token Economy

1. Never read inactive `examples/` — this repo’s Golden Path is the real app
2. Never fill `KNOWLEDGE_BASE.md` with generic framework docs
3. Update memory files only at session start, milestone end, or architectural pivot
4. Read-before-write: `@filename` before edits
5. Sequential before Parallel in `BUILD_PLAN.md`
6. Max **250** lines view / **150** lines logic (project override)

## Parallel Guardrails

- Branch: `feature/agent-[task-name]` per agent, separate worktree when needed
- No overlapping file scopes (`docs/PARALLEL_AGENT_SCOPES.md`)
- Shared schema/types: sequential agent only first
- Parallel agents never edit `BUILD_PLAN.md`

## Status markers

- **`BUILD_PLAN.md`:** 🔲 open · ✅ done · ❌ blocked (emoji only)
- **`docs/EXECUTION_PLAN.md`:** `- [ ]` / `- [x]` (product board exception — see `docs/BOOTSTRAP_ALIGNMENT.md`)

## 3-Strike Rule

After 3 failed fix attempts: halt, summarize conflict, request human direction.

## Session Checkpoint

Write `.cursor-session-state` (see `.cursor-session-state.example.json`), clear chat, restore on restart, delete file when done.

## Non-regression

Do not reduce scan universe, change scan interval, or alter OHLCV provider order without explicit product approval.
Keep `scripts/ci_verify.sh` parity with Render.
