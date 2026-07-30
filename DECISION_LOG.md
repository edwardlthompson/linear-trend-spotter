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

### 2026-07-15 — Harden notification state and Tier-C provisioning
- **Status:** Accepted
- **Context:** The June notification rollout ignored Render-provisioned `NTFY_*` values, bulk-replaced worker env vars despite masked secrets, and let the onboarding guide unsubscribe active Tier-B users. Exit payloads also filtered venues against compile-time defaults instead of runtime targets.
- **Decision:** Read ntfy settings from env with config fallback, update only individual `NTFY_*` Render keys, make guide enablement idempotent, and derive exit venues from runtime target exchanges.
- **Alternatives considered:** Continue full env-list PUT with a risk override; require `config.json` edits on Render; retain toggle behavior in all Tier-B entry points.
- **Consequences:** Provisioning cannot erase unrelated worker secrets, env-only Tier-C deployments work, and active push subscriptions/exchange-filtered exits are preserved. Validated by 13 focused tests and `scripts/ci_verify.sh` (90 tests).

