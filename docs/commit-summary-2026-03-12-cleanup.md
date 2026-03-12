# Commit Summary (2026-03-12 Cleanup)

## Scope

- Removed runtime-generated artifacts from repository root.
- Pruned generated artifact outputs from `.archive` while keeping archived source/docs.

## Why This Change

- Runtime outputs should not remain in version control working state.
- Archived generated binaries/logs were unnecessary for ongoing development and increased workspace noise.

## Cleanup Details

- Deleted root runtime artifacts:
  - `backtest_results.json`
  - `metrics.json`
- Deleted archived generated outputs:
  - backtest JSON outputs in `.archive`
  - scanner/backtest log outputs in `.archive`
  - generated PNG artifacts in `.archive`
  - archived `.db` snapshots in `.archive`

## Preserved Archive Content

- Kept archived source/docs/scripts (`.py`, `.md`, `.pdf`, `.sh`, `.txt`) and config backup variants.

## Files

- `docs/commit-summary-2026-03-12-cleanup.md`
- `.archive/*` (selected generated artifacts removed)
- `backtest_results.json` (deleted)
- `metrics.json` (deleted)
