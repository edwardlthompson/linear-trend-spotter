# Commit Summary (2026-03-12 Cooldown 6h)

## Scope

- Reduced the default re-entry cooldown window from 24 hours to 6 hours.
- Updated user-facing docs and config example to match runtime behavior.

## Why This Change

- Re-entry suppression was too long for the current scan cadence and reduced responsiveness.
- A 6-hour default keeps churn protection while allowing faster recovery when symbols re-qualify.

## Changes

- `config/settings.py`
  - Default `ALERT_COOLDOWN_HOURS` changed from `24` to `6`.
  - Fallback value in `alert_cooldown_hours` property changed from `24` to `6`.
- `config.json.example`
  - Added explicit `ALERT_COOLDOWN_HOURS: 6` entry.
- `README.md`
  - Updated cooldown narrative and config table default from 24 to 6.

## Files

- `config/settings.py`
- `config.json.example`
- `README.md`
- `docs/commit-summary-2026-03-12-cooldown-6h.md`
