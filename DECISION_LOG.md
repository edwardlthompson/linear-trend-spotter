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


### 2026-07-07 — Critical scan and notification regression fixes
- **Status:** Accepted
- **Context:** Daily critical-bug automation found healthy zero-result scans returning before active-exit reconciliation, env-only NTFY settings not being read, Render ntfy provisioning using bulk env replacement, runtime MEXC exits filtered by default exchanges, and dashboard notification/service-worker regressions from missing precache assets and poll fallback side effects.
- **Decision:** Apply targeted fixes only: route zero-result scanner branches through empty-snapshot/exit notification finalization; read `NTFY_*` env overrides; update only per-key `NTFY_*` Render vars; infer exit venues from runtime `TARGET_EXCHANGES`; remove missing dashboard precache/manifest references and suppress poll/fallback notification side effects.
- **Alternatives considered:** Broad scanner orchestration refactor; adding generated PNG asset pipeline; preserving bulk Render env PUT with extra guards.
- **Consequences:** Stale active rows and missed exit alerts are prevented for legitimate zero-qualified scans, ntfy provisioning cannot wipe unrelated secrets, and dashboard notification substrates install reliably. Validated with `bash scripts/ci_verify.sh` (92 pytest tests).
