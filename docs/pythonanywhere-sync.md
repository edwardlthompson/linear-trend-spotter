# GitHub → PythonAnywhere Sync Automation

This project includes a GitHub Actions workflow that triggers a `git` sync command on PythonAnywhere after pushes to `main`.

## What was added

- Workflow: `.github/workflows/sync-pythonanywhere.yml`
- API runner script: `.github/scripts/pythonanywhere_sync.py`

## Required GitHub repository secrets

Set these in **Settings → Secrets and variables → Actions → New repository secret**:

- `PA_USERNAME` (your PythonAnywhere username)
- `PA_API_TOKEN` (PythonAnywhere API token)
- `PA_PROJECT_PATH` (absolute path of your project on PythonAnywhere, example: `/home/<username>/linear-trend-spotter`)

Optional secrets:

- `PA_BRANCH` (default: `main`)
- `PA_INSTALL_REQUIREMENTS` (`true` or `false`, default: `false`)
- `PA_VENV_PYTHON` (example: `/home/<username>/.virtualenvs/venv-name/bin/python`)
- `PA_POST_SYNC_COMMAND` (any extra command to run after sync)
- `PA_SSH_PRIVATE_KEY` (recommended for unattended deploys; if set, workflow uses SSH mode and skips console API mode)

If `PA_PROJECT_PATH` is not set, the workflow now falls back to `/home/<PA_USERNAME>/<repo-name>` using `GITHUB_REPOSITORY`.

## How it works

On push to `main` (or manual run), GitHub Actions calls the PythonAnywhere API and sends this command to a bash console:

1. `cd <PA_PROJECT_PATH>`
2. `git fetch origin <PA_BRANCH>`
3. `git reset --hard origin/<PA_BRANCH>`
4. `git clean -fd`
5. Optional dependency install and post-sync command

## First-time PythonAnywhere setup

1. Ensure your project exists on PythonAnywhere and has a Git remote named `origin`.
2. Ensure PythonAnywhere can access your GitHub repo (HTTPS auth or SSH key setup on PythonAnywhere).
3. Create/verify your virtualenv path if you enable `PA_INSTALL_REQUIREMENTS=true`.

## Trigger options

- Automatic on push to `main`
- Manual from **Actions → Sync to PythonAnywhere → Run workflow**

## Notes

- The API call queues the command in a PythonAnywhere bash console.
- If you need strict deployment verification, inspect console output on PythonAnywhere after the workflow run.
- Workflow preflight now fails early with clear errors if `PA_USERNAME` or `PA_API_TOKEN` is missing.
- PythonAnywhere console API cannot start console processes by itself; if no console has been browser-started, API mode can fail with HTTP 412.
- To avoid that limitation in CI, set `PA_SSH_PRIVATE_KEY` and use SSH mode.
