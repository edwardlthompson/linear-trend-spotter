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

### 2026-07-16 — Preserve notification state across zero-result scans and provisioning
- **Status:** Accepted
- **Context:** Recent notification changes left healthy zero-result scans unable to finalize exits, ignored Render-provisioned `NTFY_*` values, and used a replace-all Render environment update that could erase unrelated secrets.
- **Decision:** Finalize healthy empty scans through the normal exit/snapshot/notification path, read explicit ntfy environment overrides, write only managed `NTFY_*` Render keys, and keep committed dashboard fallbacks from advancing live notification state.
- **Alternatives considered:** Preserve the early returns; bulk-rewrite all Render environment variables after parsing/masking; treat committed fallback data as live.
- **Consequences:** Exit alerts and empty snapshots remain accurate, Tier-C works with documented Render configuration, and provisioning cannot overwrite unrelated secrets. Validated with 16 focused regressions and `scripts/ci_verify.sh` (93 tests plus lint, types, imports, compileall, and backtest smoke checks).

