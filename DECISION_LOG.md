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

### 2026-07-14 — Preserve notification state across empty scans and service migrations
- **Status:** Accepted
- **Context:** Recent scanner and notification changes could skip exit finalization on healthy zero-result scans, ignore Render-only ntfy configuration, erase masked Render environment values during provisioning, omit configured exchange metadata from exits, and leave existing browser push subscriptions absent from a new persistent relay store.
- **Decision:** Route healthy zero-result scans through shared snapshot/exit finalization; overlay `NTFY_*` environment settings; update only managed ntfy keys through Render's per-key API; derive exit venues from runtime targets; re-register existing browser subscriptions on dashboard load; use committed snapshots for live-fetch failures without advancing alert baselines.
- **Alternatives considered:** Preserve early returns and rely on a later non-empty scan; require operators and users to manually rewrite config or re-subscribe; retain bulk environment replacement with a warning.
- **Consequences:** Empty qualified sets and relay migrations no longer silently lose exit state or notifications. Validation passed with 17 focused regression tests and the full `scripts/ci_verify.sh` suite (94 tests).

