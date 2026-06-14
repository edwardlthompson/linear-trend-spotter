# Linear Trend Spotter — Windows tray notifier (Q24 scaffold)

MIT-licensed companion that polls the **public qualified snapshot URL** and shows a native toast when the filtered qualified row set changes (same semantics as dashboard Tier-A).

## Requirements

- Python 3.11+
- Windows 10/11
- `pip install -r requirements.txt`

## Configure

Set environment variables (or a `.env` file loaded by your launcher):

| Variable | Description |
|----------|-------------|
| `LTS_SNAPSHOT_URL` | HTTPS URL to `qualified_public_snapshot.json` |
| `LTS_POLL_INTERVAL_SECONDS` | Poll interval (default `3600`, min `900`) |
| `LTS_TARGET_EXCHANGES` | Optional comma list, e.g. `coinbase,kraken` |

## Run

```powershell
cd clients/windows
python tray_notifier.py
```

The app stays in the system tray. Right-click → **Quit**.

## Distribution

- GitHub Releases (portable zip) — set `window.__WINDOWS_TRAY_RELEASE_URL__` in dashboard `config.js` for the notification guide link
- [winget](https://github.com/microsoft/winget-pkgs) manifest in `winget/LinearTrendSpotter.TrayNotifier.yaml`

### winget automation

```powershell
# Validate manifest (skips if winget CLI absent)
powershell -File scripts/winget_validate.ps1

# After publishing a GitHub Release asset:
$env:LTS_TRAY_RELEASE_URL = "https://github.com/.../releases/download/v0.1.0/tray-notifier-win-x64.zip"
$env:LTS_TRAY_SHA256 = "..."   # optional; updates manifest before PR
powershell -File scripts/winget_submit.ps1
```

Microsoft maintainer review/merge on `winget-pkgs` remains a manual external step.

## FOSS

No proprietary SDKs. Uses snapshot JSON only — no market API calls from the client.
