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

