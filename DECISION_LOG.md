# Decision Log

> Chronological register of major technical trade-offs, accepted architectures, and rejected alternatives.
> **Treat past entries as immutable history; append only.**

## Format

```markdown
### YYYY-MM-DD — [Title]
- **Status:** Accepted | Rejected | Superseded
- **Context:** ...
- **Decision:** ...
- **Alternatives considered:** ...
- **Consequences:** ...
```

## Entries

### 2026-07-21 — Align with agent-project-bootstrap v0.15.0
- **Status:** Accepted
- **Context:** Repo was pinned at template v0.2.1 while upstream advanced to v0.15.0. A partial uncommitted v0.14.1 WIP existed; human approved finishing at v0.15.0 with recommended defaults.
- **Decision:** Additive migration per `docs/BOOTSTRAP_ALIGNMENT.md`: FOSS Cursor surface (rules/commands/hooks/skills/worktrees/local-compute), emoji `BUILD_PLAN` lanes, merged `validate-bootstrap`, Scorecard-only CI expansion, pin `.template-version` to 0.15.0. Keep EXECUTION_PLAN GitHub checkboxes; keep 250/150 line limits; do not copy `examples/` or adopt release-please/automerge/stale/pages.
- **Alternatives considered:** Stop at unfinished v0.14.1 WIP; full upstream CI set; adopt 300-line view limit; emoji migration of EXECUTION_PLAN; defer hooks.
- **Consequences:** Agents use START_HERE → CURSOR_MODES → BUILD_PLAN Sequential; dual-board status convention; `[HUMAN]` items remain for Private vuln reporting and Scorecard badge confirmation.

### 2026-06-13 — Snapshot relay persistent disk deferred
- **Status:** Accepted
- **Context:** Sprint 4 optional task considered adding a Starter+ persistent disk for `snapshot_server` so `/tmp/qualified_public_snapshot.json` survives redeploys.
- **Decision:** Keep free-tier ephemeral store; worker reposts snapshot after each scan; `/relay-health` confirms ingest.
- **Alternatives considered:** Starter+ disk (~$0.25/GB/mo); GitHub Pages-only snapshot without relay.
- **Consequences:** Brief empty dashboard window after relay redeploy until next worker POST; acceptable for current ops.

