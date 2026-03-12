# Commit Summary (2026-03-12)

## Scope

- Added explicit runtime log marker for per-scan active ranking summary sends.
- Updated notification documentation to cover active ranking summary behavior and payload details.
- Captured this change set in a dated commit summary.

## Why This Change

- Full scans can produce very large logs; a deterministic marker is needed to verify summary-notification execution without inspecting full Telegram payload output.
- Notification docs needed to reflect the new behavior: active ranking summary is sent each scan when Telegram is enabled.

## Code Changes

- `main.py`
  - Added summary send counter and marker log line:
    - `📌 ACTIVE_RANKING_SUMMARY_SENT messages=<sent>/<total> active_coins=<count>`
  - Marker is emitted after active ranking summary message dispatch loop.

## Documentation Changes

- `README.md`
  - Added `Per-scan active ranking summary` section under notification behavior.
  - Documented rank arrows and the two gain baselines:
    - since first announcement (entry baseline)
    - since prior hourly update (previous active-state baseline)
  - Added `NO_CHANGE_NOTIFICATIONS` row to config table and clarified that per-scan ranking summary still sends when Telegram is enabled.

## Behavior Note

- This intentionally deviates from older no-change-only summary semantics.
- New behavior: ranking summary sends every scan (when Telegram is configured), regardless of whether entries/exits occurred.

## Files

- `main.py`
- `README.md`
- `docs/commit-summary-2026-03-12.md`
