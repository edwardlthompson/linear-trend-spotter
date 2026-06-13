# Module C: Python Applications

> Active for Linear Trend Spotter worker, backtesting, and Flask microservices.

## Requirements (Verbatim)

- **Environment & Dependency Locking:** Enforce strict package pinning via `uv.lock` and [pyproject.toml](../pyproject.toml).
- **Static Analysis & Type Hygiene:** ruff lint in CI; incremental mypy on `config` and `notifications`.

## Activation Checklist

- [x] Create `pyproject.toml` with dependency pins
- [x] Generate and commit `uv.lock`
- [x] Enable `ruff check` in CI via `scripts/ci_verify.sh`
- [x] Enable `mypy` in CI (scoped packages)
- [x] Golden Path: `scripts/ci_verify.sh` (not `examples/python/`)
- [ ] Set coverage budget threshold in CI
- [x] Pre-commit ruff hook
- [ ] OpenAPI/schema-first design if exposing HTTP API
- [ ] Contract tests for public API boundaries

## Operations (when deployed as service)

- [x] Health/readiness: snapshot relay `GET /relay-health` (see `docs/RUNBOOK.md`)
- [ ] Structured logging (JSON, correlation IDs, no PII)

## Golden Path Reference

See [scripts/ci_verify.sh](../scripts/ci_verify.sh) and worker entrypoints `main.py`, `scheduler.py`.

## Owner Labels for This Module

| Task type | Label |
|-----------|-------|
| Scaffold package, types, tests | `AGENT` |
| Dependency audit approval | `HUMAN` |
| ruff/mypy/pytest CI gates | `AUTO` |
