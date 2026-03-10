# Render Migration (Simple Setup)

This repo now supports Render deployment via `render.yaml` and a disk-backed worker process.

## What changed

- Added `render.yaml` (Render Blueprint)
- Added `scripts/run_render_worker.sh` (continuous hourly scheduler loop)
- Added `DATA_DIR` support in `config/settings.py` for DB/log/artifact persistence
- Updated `scheduler.py` to use settings-managed paths
- Disabled automatic PythonAnywhere sync on push (`.github/workflows/sync-pythonanywhere.yml` now manual only)

## Manual setup in Render (very simple)

1. Push code to GitHub (includes `render.yaml`).
2. In Render Dashboard, click **New +** → **Blueprint**.
3. Select this GitHub repo and branch (`main`).
4. Render will detect `render.yaml` and create `linear-trend-spotter-worker`.
5. Enter secret values when prompted (`CMC_API_KEY`, `TELEGRAM_BOT_TOKEN`, etc.).
6. Create the service.
7. After first deploy, check logs for:
   - `Render worker started`
   - `Starting scheduled scan`

## Notes

- This design uses a **background worker + persistent disk**, not a Render cron job.
- Reason: Render cron jobs cannot attach/access persistent disks.
- Persisted runtime data is written under `DATA_DIR` (set to `/var/data` in `render.yaml`).

## Manual trigger (one-off test)

From Render service Shell, run:

```bash
cd /opt/render/project/src
python3 scheduler.py
```

## Useful log paths on Render

- Worker log file: `/var/data/logs/render_worker.log`
- App log file: `/var/data/trend_scanner.log`
- Stats file: `/var/data/scan_stats.json`
