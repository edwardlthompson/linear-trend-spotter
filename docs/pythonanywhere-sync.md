# GitHub → PythonAnywhere Sync Automation

This project includes a GitHub Actions workflow that triggers a `git` sync command on PythonAnywhere after pushes to `main`.

## What was added

- Workflow: `.github/workflows/sync-pythonanywhere.yml`
- API runner script: `.github/scripts/pythonanywhere_sync.py`

## Required GitHub repository secrets

Set these in **Settings → Secrets and variables → Actions → New repository secret**:

- `PA_USERNAME` (your PythonAnywhere username)
- `PA_API_TOKEN` (PythonAnywhere API token)
- `PA_PROJECT_PATH` (absolute path of your project on PythonAnywhere, example: `/home/edwardlthompson/linear-trend-spotter`)

Optional secrets:

- `PA_BRANCH` (default: `main`)
- `PA_INSTALL_REQUIREMENTS` (`true` or `false`, default: `false`)
- `PA_VENV_PYTHON` (example: `/home/edwardlthompson/.virtualenvs/venv-name/bin/python`)
- `PA_POST_SYNC_COMMAND` (any extra command to run after sync)
- `PA_SSH_PRIVATE_KEY` (recommended for unattended deploys; if set, workflow uses SSH mode and skips console API mode)
- `PA_ALLOW_CONSOLE_MODE` (`true` to allow console API fallback when `PA_SSH_PRIVATE_KEY` is not set; default behavior is blocked)

For this project, set `PA_USERNAME=edwardlthompson`.

If `PA_PROJECT_PATH` is not set, the workflow now falls back to `/home/<PA_USERNAME>/<repo-name>` using `GITHUB_REPOSITORY` (for your repo: `/home/edwardlthompson/linear-trend-spotter`).

## How it works

On push to `main` (or manual run), GitHub Actions runs in this order:

1. Validate required config/secrets.
2. If `PA_SSH_PRIVATE_KEY` is set (recommended): connect over SSH and run sync commands directly.
3. Else, if `PA_ALLOW_CONSOLE_MODE=true`: call PythonAnywhere console API mode.
4. Else: fail fast with a clear configuration error.

The sync command is:

1. `cd <PA_PROJECT_PATH>`
2. `git fetch origin <PA_BRANCH>`
3. `git reset --hard origin/<PA_BRANCH>`
4. `git clean -fd`
5. Optional dependency install and post-sync command

## First-time PythonAnywhere setup

1. Ensure your project exists on PythonAnywhere and has a Git remote named `origin`.
2. Add your deploy public key to `~/.ssh/authorized_keys` on PythonAnywhere (documented best practice).
3. Ensure PythonAnywhere can pull your GitHub repo (SSH deploy key on GitHub repo or working HTTPS credentials).
4. Create/verify your virtualenv path if you enable `PA_INSTALL_REQUIREMENTS=true`.

### Adding the SSH key on PythonAnywhere (recommended methods)

Method A (most reliable): PythonAnywhere Bash console

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys
```

Then paste your public key line, press Enter, and finish with `Ctrl+D`.

Method B: Files tab editor

1. Open **Files** in PythonAnywhere.
2. Navigate to `.ssh/authorized_keys` (create folder/file if missing).
3. Paste one public key per line and save.

Reference: PythonAnywhere SSH docs explain that passwordless login keys go in `~/.ssh/authorized_keys`.

## Trigger options

- Automatic on push to `main`
- Manual from **Actions → Sync to PythonAnywhere → Run workflow**

## Troubleshooting: project path not found

If you see:

- `cd: /home/edwardlthompson/linear-trend-spotter: No such file or directory`
- `fatal: not a git repository`

then your project has not been cloned on PythonAnywhere yet (or is in a different path).

### One-time bootstrap on PythonAnywhere

In a PythonAnywhere Bash console:

```bash
cd /home/edwardlthompson
ls -la
```

If `linear-trend-spotter` is missing, clone it:

```bash
git clone git@github.com:edwardlthompson/linear-trend-spotter.git /home/edwardlthompson/linear-trend-spotter
cd /home/edwardlthompson/linear-trend-spotter
git remote -v
git fetch origin main
```

If the clone/fetch fails with permission errors, add the **PythonAnywhere account SSH public key** as a deploy key (read access) in the GitHub repo and retry.

After bootstrap, keep this secret set in GitHub Actions:

- `PA_PROJECT_PATH=/home/edwardlthompson/linear-trend-spotter`

## Notes

- SSH mode is preferred for unattended CI and does not depend on browser-started consoles.
- Console API mode queues commands in a PythonAnywhere bash console.
- If you need strict deployment verification, inspect console output on PythonAnywhere after the workflow run.
- Workflow preflight now fails early with clear errors if `PA_USERNAME` or `PA_API_TOKEN` is missing.
- PythonAnywhere console API cannot start console processes by itself; if no console has been browser-started, API mode can fail with HTTP 412.
- To avoid that limitation in CI, set `PA_SSH_PRIVATE_KEY` and use SSH mode.
- Console API fallback is now blocked by default; set `PA_ALLOW_CONSOLE_MODE=true` only if you intentionally want API mode.
