# Completed Tasks

> Archive of finished BUILD_PLAN items. Open work remains in `BUILD_PLAN.md`.

## Sprint 0 -- Bootstrap Adoption

- [x] [AGENT] Copy bootstrap scaffold (`.cursor/rules`, agent memory, legal, docs, scripts, `.devcontainer`)
- [x] [AGENT] Set CODEOWNERS to `@edwardlthompson`; run init customization
- [x] [AGENT] Customize `AGENTS.md`, `AGENT_MEMORY.md`, `BUILD_PLAN.md`, `TEMPLATE_INDEX.json`
- [x] [AGENT] Add MIT `LICENSE`, `THIRD_PARTY_LICENSES.md`, community docs
- [x] [AGENT] Draft `docs/THREAT_MODEL.md`, `docs/PRIVACY.md`, `docs/RUNBOOK.md`
- [x] [AUTO] `scripts/validate-bootstrap.sh` passes
- [x] [AGENT] Merge copilot-instructions into AGENTS.md
- [x] [AUTO] Enable Dependabot alerts + security updates (`scripts/apply-github-repo-settings.sh`)
- [x] [AUTO] Branch protection on `main`: Verify, Trivy FS Scan, Analyze (python); enforce admins
- [x] [HUMAN] Approve Sprint 0 after CI green on `main`
- [x] [HUMAN] Configure `.template-update.json` interval (weekly; first check recorded)
- [x] [HUMAN] GitHub repo About configured (project description + topics live on GitHub)

## Sprint 1 -- uv + CI Parity

- [x] [AGENT] Consolidate deps in `pyproject.toml`; generate `uv.lock`
- [x] [AGENT] Update `scripts/ci_verify.sh`, `render.yaml`, pre-commit to `uv sync --locked`
- [x] [AGENT] Merge bootstrap guardrail jobs into `.github/workflows/ci.yml`
- [x] [AGENT] Add CodeQL, Trivy, dependency-review, health-check, release workflows
- [x] [AGENT] Extend `scripts/check_github_ci.py` for CI + Security Scan + CodeQL
- [x] [AUTO] Full CI matrix green on `main`
- [x] [AGENT] Export legacy `requirements*.txt` from uv
- [x] [AGENT] Expand pre-commit hooks (Sprint 4 improved Windows cross-platform)
- [x] [AGENT] Update README quick-start to uv
- [x] [HUMAN] Sign off Sprint 1

## Sprint 1b -- Render and Local Runtime Parity (P0)

- [x] [AGENT] Add shared helper `scripts/render_uv_run.sh`
- [x] [AGENT] Update `render.yaml` start commands for worker, push, snapshot
- [x] [AGENT] Update `scripts/run_render_worker.sh` to use `uv run python scheduler.py`
- [x] [AGENT] Align `docker-compose.yml` with `scripts/ci_verify.sh`
- [x] [AGENT] Update `docs/render-setup.md` and `docs/RUNBOOK.md` for `uv run`
- [x] [AGENT] Fix stale `render.yaml` build comment
- [x] [AGENT] Add test: uv-run gunicorn import smoke from `push_server/` cwd
- [x] [AGENT] Document Render redeploy checklist in RUNBOOK
- [x] [AUTO] Render services healthy: push `/health`, snapshot `/relay-health` (pre-merge smoke)
- [x] [AUTO] `ci_verify.sh` equivalent green locally; GitHub CI green on `main`
- [x] [HUMAN] Redeploy all three Render services (auto-deploy on merge to `main`)

## Sprint 2 -- Compliance and Documentation Truth (P1-P2)

- [x] [AGENT] Retarget `scripts/check-license-compliance.sh` to root `pyproject.toml` / `uv.lock`
- [x] [AGENT] Wire license check into `.github/workflows/ci.yml`
- [x] [AGENT] Populate `THIRD_PARTY_LICENSES.md`; accurate CI claim
- [x] [AGENT] Rewrite `CONTRIBUTING.md` for Linear Trend Spotter
- [x] [AGENT] Replace `CHANGELOG.md` template history with project entry
- [x] [AGENT] Customize `modules/python/MODULE.md` and `modules/web/MODULE.md`
- [x] [AGENT] Expand `TEMPLATE_INDEX.json` with project-critical paths
- [x] [AGENT] EXECUTION_PLAN footnote: historical pip refs, current path is uv
- [x] [AGENT] Update `linear-trend-spotter-spec.md` deps section
- [x] [AGENT] Prune template KB entries; add LTS uv/Render entry in `KNOWLEDGE_BASE.md`
- [x] [AGENT] Deduplicate CI gate docs to canonical `check_github_ci.py`
- [x] [AUTO] `validate-template-index.sh` and license compliance green locally

## Sprint 3 -- Security Gates and Human Sign-off

- [x] [AGENT] Triage and resolve open Dependabot alerts on `pytest` (bump to 9.0.3, `uv lock`, tests)
- [x] [AGENT] Gate `release.yml` on `check-github-ci.sh`
- [x] [HUMAN] Dependabot + branch protection configured via `apply-github-repo-settings.sh`
- [x] [HUMAN] First weekly CVE triage: pytest GHSA-6w46-j5rx-g56g remediated (moderate)
- [x] [HUMAN] Sign off Sprint 1 and Sprint 1b after Render smoke + CI green
- [x] [AUTO] `python scripts/check_github_ci.py --wait 300` after merge
- [x] [AUTO] Run first `check-template-updates.sh`; set `last_checked` in `.template-update.json`

## Sprint 4 -- Tooling Hardening

- [x] [AGENT] Cross-platform pre-commit hooks
- [x] [AGENT] Extend `validate-bootstrap.sh` optional `ci_verify.sh` (`VALIDATE_BOOTSTRAP_FULL=1`)
- [x] [AGENT] Mojibake grep in encoding check (`scripts/check-file-encoding.sh`)
- [x] [HUMAN] Snapshot relay persistent disk deferred (see `DECISION_LOG.md`)

## Milestone Gates (completed)

- [x] [AUTO] `scripts/validate-bootstrap.sh` green
- [x] [AUTO] `scripts/ci_verify.sh` green (local + Render build)
- [x] [AUTO] Required workflows: CI, Security Scan, CodeQL
- [x] [AUTO] Render worker + both relays start with `uv run` (relay-health + push /health OK)
- [x] [AUTO] `docker-compose.yml` command matches `ci_verify.sh`
- [x] [AUTO] License compliance step in CI green on `main`
- [x] [HUMAN] Zero open Critical/High Dependabot alerts (pytest moderate remediated)
- [x] [HUMAN] Branch protection enforced (`enforce_admins: true`)
- [x] [HUMAN] `CHANGELOG.md` has project release entry

## Tooling added

- [x] [AGENT] `scripts/apply-github-repo-settings.sh` — automates Dependabot, branch protection, optional About sync
