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

### 2026-07-21 — /push bootstrap alignment to main
- **Status:** Accepted
- **Context:** /push after A15 alignment commit 84efc0d; child-repo gates green; Release Please workflows not adopted.
- **Decision:** Push main with template pin 0.15.0; skip merge-release-please-pr; keep product package version 0.0.0; ephemeral RELEASE_NOTES.md only.
- **Alternatives considered:** Cut product semver; enable release-please workflows now.
- **Consequences:** CI must stay green on main; HUMAN items remain for Private vuln reporting and Scorecard badge.

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


### 2026-07-07 — Critical scan and notification regression fixes
- **Status:** Accepted
- **Context:** Daily critical-bug automation found healthy zero-result scans returning before active-exit reconciliation, env-only NTFY settings not being read, Render ntfy provisioning using bulk env replacement, runtime MEXC exits filtered by default exchanges, and dashboard notification/service-worker regressions from missing precache assets and poll fallback side effects.
- **Decision:** Apply targeted fixes only: route zero-result scanner branches through empty-snapshot/exit notification finalization; read `NTFY_*` env overrides; update only per-key `NTFY_*` Render vars; infer exit venues from runtime `TARGET_EXCHANGES`; remove missing dashboard precache/manifest references and suppress poll/fallback notification side effects.
- **Alternatives considered:** Broad scanner orchestration refactor; adding generated PNG asset pipeline; preserving bulk Render env PUT with extra guards.
- **Consequences:** Stale active rows and missed exit alerts are prevented for legitimate zero-qualified scans, ntfy provisioning cannot wipe unrelated secrets, and dashboard notification substrates install reliably. Validated with `bash scripts/ci_verify.sh` (92 pytest tests).
