# Runbook

> Deploy, health checks, rollback, and escalation for Linear Trend Spotter.

## Services

| Service | Type | Blueprint name | Notes |
|---------|------|----------------|-------|
| Scanner worker | Render worker | `linear-trend-spotter-worker` | Runs `scripts/run_render_worker.sh` |
| Snapshot relay | Render web | `linear-trend-spotter-snapshot` | `rootDir: snapshot_server` |
| Push relay | Render web | `linear-trend-spotter-push` | `rootDir: push_server` |
| Dashboard | GitHub Pages | `docs/` | Static PWA at `docs/dashboard/` |

See also: [`render-setup.md`](render-setup.md), [`MANUAL_DEPLOY_STEPS.md`](MANUAL_DEPLOY_STEPS.md), [`DELIVERY_MODE.md`](DELIVERY_MODE.md).

## Deploy

### Worker (primary)

1. Merge to `main` (branch tracked by Render blueprint).
2. Render runs `bash scripts/ci_verify.sh` at build time — must pass.
3. Worker starts via `bash scripts/run_render_worker.sh`.
4. Verify logs: `Render worker started`, `Starting scheduled scan`.

### Snapshot / Push relays

- Auto-deploy on `main` commit.
- Build: `uv sync --locked --extra snapshot` or `--extra push` from repo root.
- Set secrets in Render dashboard per `.env.example`.

### Dashboard (GitHub Pages)

- Push updates to `docs/dashboard/` on `main`.
- Hard refresh or unregister service worker if UI stale (see MANUAL_DEPLOY_STEPS §4).

## Health Checks

| Check | Command / URL |
|-------|---------------|
| Local CI parity | `bash scripts/ci_verify.sh` |
| GitHub CI gate | `python scripts/check_github_ci.py` |
| Snapshot relay | `python scripts/check_snapshot_relay.py` |
| Relay health HTTP | `GET /relay-health` on snapshot service |
| Worker scan stats | `/var/data/scan_stats.json` on Render disk |

## Rollback

1. Revert commit on `main` or redeploy previous Render deploy from dashboard.
2. Snapshot relay store under `/tmp` is ephemeral — worker must POST again after rollback.
3. Persistent disk data at `/var/data` survives redeploys unless disk wiped.

## Logs

| Log | Path (Render worker) |
|-----|----------------------|
| Worker wrapper | `/var/data/logs/render_worker.log` |
| Scanner | `/var/data/trend_scanner.log` |
| Scan stats | `/var/data/scan_stats.json` |

## Escalation

1. Check latest GitHub Actions: CI, Security Scan, CodeQL
2. Review Render deploy logs and worker log files
3. Run local `bash scripts/ci_verify.sh` on failing commit
4. File security issues per [`SECURITY.md`](../SECURITY.md)

## SLOs (informal)

- Scan cadence: `SCAN_INTERVAL_SECONDS` (default 3600) — do not change without product approval
- Dashboard availability: depends on GitHub Pages + snapshot relay uptime
- CI: must be green on `main` before EXECUTION_PLAN milestone sign-off
