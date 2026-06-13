# Agent Memory

> Centralized index of tech stack, threat models, persistent context, and retrospectives.
> Update only at session startups, milestone boundaries, or major architectural pivots.

## Tech Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Worker | Python | 3.11+ | Scanner, backtesting, SQLite |
| Analytics | pandas, numpy, vectorbt | pinned in uv.lock | TA-Lib optional extra (local prod) |
| Microservices | Flask + Gunicorn | 3.x | `push_server/`, `snapshot_server/` |
| Frontend | Static PWA | vanilla JS | `docs/dashboard/` — GitHub Pages |
| Deploy | Render | blueprint | Worker + 2 web services via `render.yaml` |
| CI | uv + ruff + mypy + pytest | — | `scripts/ci_verify.sh` (Render parity) |
| License | MIT | — | Pure FOSS |

## Active Modules

- [x] Web / PWA (`modules/web/MODULE.md`) — `docs/dashboard/`
- [x] Python (`modules/python/MODULE.md`) — worker + backtesting
- [ ] Android / F-Droid — not applicable
- [ ] Lightroom Classic — not applicable

## Threat Model Checklist

- [x] `docs/THREAT_MODEL.md` drafted (STRIDE, trust boundaries, top abuse cases)
- [x] No proprietary closed-source SDKs in production path
- [x] Opt-in only telemetry (GDPR/CCPA compliant); see `docs/PRIVACY.md`
- [x] Secrets excluded from VCS (Gitleaks pre-commit + CI)
- [x] Dependency vulnerability scanning enabled (CodeQL + Trivy + Dependabot)
- [ ] Input validation at all data boundaries (ongoing per EXECUTION_PLAN)
- [ ] `SECURITY.md` and private vulnerability reporting enabled (HUMAN GitHub settings)

## Persistent Context

### Project Purpose

Crypto exchange scanner with backtesting and static PWA dashboard. Pulls exchange-listed coins, filters on volume/momentum, scores OHLCV uniformity, runs integrated backtests, and publishes qualified-coin snapshots to a public dashboard with optional Web Push notifications.

### Key Constraints

- Max 250 lines per view file, 150 lines per logic file (legacy exemptions documented in BUILD_PLAN)
- Trunk-based development with Conventional Commits
- OHLCV provider order: CoinGecko → Polygon → CoinMarketCap (never reversed for cost savings)
- Same scan universe and interval unless explicitly approved product change
- CI and Render worker use identical verify script (`scripts/ci_verify.sh`)

### Task Boards

- **Bootstrap/ops:** `BUILD_PLAN.md`
- **Product engineering:** `docs/EXECUTION_PLAN.md` (milestones A–Q)

## Session Retrospectives

| Date | Milestone | What worked | What to improve |
|------|-----------|-------------|-----------------|
| 2026-06-13 | Bootstrap adoption | Cherry-pick from agent-project-bootstrap | Lighthouse CI for dashboard deferred |

## Template Provenance

- **Source template:** `edwardlthompson/agent-project-bootstrap`
- **Template version:** `0.2.1` (see `.template-version`)
- **Last update check:** See `.template-update.json`
