"""Quiet-hours helper extracted from main scanner (Milestone I2)."""

from __future__ import annotations

from datetime import datetime, timezone


def telegram_quiet_active(
    *,
    quiet_hours_enabled: bool,
    quiet_hours_start_hour_utc: int,
    quiet_hours_end_hour_utc: int,
    is_within_utc_quiet_window,
) -> bool:
    if not quiet_hours_enabled:
        return False
    return is_within_utc_quiet_window(
        datetime.now(timezone.utc),
        quiet_hours_start_hour_utc,
        quiet_hours_end_hour_utc,
    )
