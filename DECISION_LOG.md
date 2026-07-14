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

### 2026-07-14 — Preserve notification state across empty scans and service migrations
- **Status:** Accepted
- **Context:** Recent scanner and notification changes could skip exit finalization on healthy zero-result scans, ignore Render-only ntfy configuration, erase masked Render environment values during provisioning, omit configured exchange metadata from exits, and leave existing browser push subscriptions absent from a new persistent relay store.
- **Decision:** Route healthy zero-result scans through shared snapshot/exit finalization; overlay `NTFY_*` environment settings; update only managed ntfy keys through Render's per-key API; derive exit venues from runtime targets; re-register existing browser subscriptions on dashboard load; use committed snapshots for live-fetch failures without advancing alert baselines.
- **Alternatives considered:** Preserve early returns and rely on a later non-empty scan; require operators and users to manually rewrite config or re-subscribe; retain bulk environment replacement with a warning.
- **Consequences:** Empty qualified sets and relay migrations no longer silently lose exit state or notifications. Validation passed with 17 focused regression tests and the full `scripts/ci_verify.sh` suite (94 tests).

