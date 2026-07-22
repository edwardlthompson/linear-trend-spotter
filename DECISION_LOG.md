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

### 2026-07-17 — Preserve scanner and notification state at empty/error boundaries
- **Status:** Accepted
- **Context:** Recent scanner and Tier-C changes skipped exit reconciliation on healthy zero-result scans, ignored Render-provisioned ntfy settings, and could bulk-replace Render env vars after misreading nested API rows. Exit venue inference also used defaults instead of runtime targets, while dashboard fallback/link handling could emit false state changes or accept executable URL schemes.
- **Decision:** Finalize healthy empty scans through one shared path while preserving active state on provider failure; read `NTFY_*` env overrides; update only individual managed Render env keys; infer exit venues from runtime targets; keep committed dashboard fallback out of notification baselines; allow only HTTPS ntfy subscribe links.
- **Alternatives considered:** Keep duplicated early-return handling; bulk-merge Render env values behind a warning; trust snapshot URLs because the worker normally generates them.
- **Consequences:** Exit/snapshot/notification state remains consistent, unrelated Render secrets cannot be erased by Tier-C provisioning, and untrusted ntfy link schemes are rejected. Validation: `bash scripts/ci_verify.sh` passed (94 tests), plus `node --check docs/dashboard/app.js`.

