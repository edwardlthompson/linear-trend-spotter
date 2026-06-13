# Changelog

All notable changes to **Linear Trend Spotter** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Agent bootstrap scaffolding from [agent-project-bootstrap](https://github.com/edwardlthompson/agent-project-bootstrap) v0.2.1
- `uv.lock` + consolidated `pyproject.toml` dependency management
- CodeQL, Trivy, dependency-review, health-check, and release GitHub workflows
- Security docs: `docs/THREAT_MODEL.md`, `docs/PRIVACY.md`, `docs/RUNBOOK.md`
- `scripts/render_uv_run.sh` for Render runtime uv venv parity

### Changed

- CI and Render worker build use `scripts/ci_verify.sh` with `uv sync --locked --extra dev`
- Push/snapshot Render services use uv extras instead of per-service `requirements.txt`
- `docker-compose.yml` mirrors full `ci_verify.sh` chain

### Fixed

- Render start commands now use `uv run` so runtime matches build-time `.venv`

---

Scaffolding derived from [agent-project-bootstrap](https://github.com/edwardlthompson/agent-project-bootstrap).
