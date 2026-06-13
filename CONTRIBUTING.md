# Contributing

Thank you for contributing to **Linear Trend Spotter** — a crypto exchange scanner with backtesting and a static PWA dashboard.

## Who contributes what

| Label | Contributor | Examples |
|-------|-------------|----------|
| `AGENT` | Cursor Agent | Scaffolding, tests, CI config, docs |
| `HUMAN` | Human developer | Approvals, credentials, product decisions |
| `AUTO` | CI/scripts | GitHub Actions, Dependabot, pre-commit |

## Getting started

1. Fork the repository and create a feature branch.
2. Read `docs/START_HERE.md`, `AGENTS.md`, and `CODE_OF_CONDUCT.md`.
3. Report security issues via `SECURITY.md` (private reporting preferred).
4. Install deps: `uv sync --locked --extra dev`
5. Run checks: `bash scripts/ci_verify.sh`
6. Open a PR using the provided template.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/).

## Pre-commit hooks

```bash
uv sync --locked --extra dev
uv run pre-commit install
uv run pre-commit run --all-files
```

## CI gate

Before merging to `main`, ensure `python scripts/check_github_ci.py` reports CI, Security Scan, and CodeQL green.

## Security triage

Maintainers run a weekly CVE triage pass per `docs/SECURITY_TRIAGE.md`.

## Task boards

- Bootstrap/ops: `BUILD_PLAN.md`
- Product engineering: `docs/EXECUTION_PLAN.md`
