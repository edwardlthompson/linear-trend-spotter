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

### 2026-07-16 — Preserve notification state across zero-result scans and provisioning
- **Status:** Accepted
- **Context:** Recent notification changes left healthy zero-result scans unable to finalize exits, ignored Render-provisioned `NTFY_*` values, and used a replace-all Render environment update that could erase unrelated secrets.
- **Decision:** Finalize healthy empty scans through the normal exit/snapshot/notification path, read explicit ntfy environment overrides, write only managed `NTFY_*` Render keys, and keep committed dashboard fallbacks from advancing live notification state.
- **Alternatives considered:** Preserve the early returns; bulk-rewrite all Render environment variables after parsing/masking; treat committed fallback data as live.
- **Consequences:** Exit alerts and empty snapshots remain accurate, Tier-C works with documented Render configuration, and provisioning cannot overwrite unrelated secrets. Validated with 16 focused regressions and `scripts/ci_verify.sh` (93 tests plus lint, types, imports, compileall, and backtest smoke checks).

