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
