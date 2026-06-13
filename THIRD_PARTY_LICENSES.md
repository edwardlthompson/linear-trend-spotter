# Third-Party Licenses

> Dependency license summary for Linear Trend Spotter. Regenerate with:
> `uv sync --locked --extra dev && uv run pip-licenses --format=markdown --with-urls`

## Project License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).

## CI Enforcement

`[AUTO]` CI runs `scripts/check-license-compliance.sh` on each push (Verify job).
The script fails on **GPL, AGPL, LGPL, and SSPL** licenses in the locked dependency tree.

## Regenerate full table

```bash
uv sync --locked --extra dev
uv run pip-licenses --format=markdown --with-urls > /tmp/licenses.md
```

## Direct runtime dependencies (from pyproject.toml)

| Package | Declared in | Notes |
|---------|-------------|-------|
| requests | `[project]` | HTTP client |
| portalocker | `[project]` | File locking |
| python-dotenv | `[project]` | Env loading |
| pandas / numpy | `[project]` | Data frames |
| vectorbt | `[project]` | Backtesting |
| tabulate | `[project]` | CLI tables |
| matplotlib | `[project]` | Charts |
| psutil | `[project]` | System metrics |
| flask / gunicorn / pywebpush | `[project.optional-dependencies]` push/snapshot/dev | Relay services |

## Incompatible Licenses

`[HUMAN]` must approve any dependency with copyleft licenses (GPL, AGPL) that
may affect distribution. Document exceptions in `DECISION_LOG.md`.

## Attribution

When bundling dependencies in releases, include this file or a generated `NOTICE`
file in the distribution artifact.
