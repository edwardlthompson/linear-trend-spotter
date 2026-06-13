# Knowledge Base

> Repository of stack-specific edge cases, resolved bugs, and reusable project solutions.

## How to use

1. Add entries only after resolving a non-obvious issue specific to this project.
2. Include: symptom, root cause, fix, and prevention.
3. Link to relevant PRs when available.

## Entries

### KB-001 — UTF-16 file corruption on Windows

| Field | Detail |
|-------|--------|
| **Symptom** | `check-json` / `json.load` fails; git ignore rules stop working |
| **Cause** | Editor saves text as UTF-16 LE (NUL bytes between ASCII chars) |
| **Fix** | Rewrite affected files with UTF-8; re-run `scripts/check-file-encoding.sh` |
| **Prevention** | Bulk edits via Python/PowerShell UTF-8 write; include root `.gitignore` in encoding scan |

### KB-002 — Render runtime missing uv venv deps

| Field | Detail |
|-------|--------|
| **Symptom** | Push/snapshot relay fails at start with `ModuleNotFoundError: flask`; worker may miss pandas/vectorbt |
| **Cause** | `uv sync` writes `.venv` at repo root during build; start commands used bare `python3` / `gunicorn` outside venv |
| **Fix** | Use `scripts/render_uv_run.sh` for all Render start commands; `uv run python scheduler.py` in worker loop |
| **Prevention** | Keep build (`ci_verify.sh` / `uv sync`) and start (`render_uv_run.sh`) paired; see Sprint 1b in BUILD_PLAN |

### KB-003 — Invalid GitHub Action bare-semver refs

| Field | Detail |
|-------|--------|
| **Symptom** | Security Scan workflow fails at setup: action version not found |
| **Cause** | Bare semver `@0.28.0` is not a valid GitHub Action ref tag |
| **Fix** | Pin to full SHA with version comment |
| **Prevention** | Run `validate-workflow-actions.sh` pre-push; `check-workflow-action-ref-format.sh` in pre-commit |

### KB-004 — docker-compose drift from CI

| Field | Detail |
|-------|--------|
| **Symptom** | Local docker smoke passes but CI fails (or vice versa) |
| **Cause** | `docker-compose.yml` used partial pip install instead of full `ci_verify.sh` |
| **Fix** | Run `bash scripts/ci_verify.sh` inside compose service |
| **Prevention** | Single canonical verify script shared by GitHub Actions, Render build, and docker-compose |

### KB-005 — License compliance script no-op

| Field | Detail |
|-------|--------|
| **Symptom** | `check-license-compliance.sh` passes without checking deps |
| **Cause** | Template script targeted non-existent `examples/python` |
| **Fix** | Retarget to root `uv.lock` + `pip-licenses --allow-only` after `uv sync --extra dev` |
| **Prevention** | Wire license step in `.github/workflows/ci.yml` Verify job |
