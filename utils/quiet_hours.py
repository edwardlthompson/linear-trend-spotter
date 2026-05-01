"""UTC quiet-window helpers for Telegram non-critical suppression."""

from __future__ import annotations

from datetime import datetime


def is_within_utc_quiet_window(now_utc: datetime, start_hour: int, end_hour: int) -> bool:
    """Return True when the UTC hour of ``now_utc`` lies inside the configured window.

    * Non-wrapping window (``start_hour < end_hour``): ``start_hour <= hour < end_hour``.
    * Wrapping window (``start_hour > end_hour``), e.g. 22→06: ``hour >= start_hour`` or ``hour < end_hour``.
    * If ``start_hour == end_hour``, the window is treated as empty (always False) so misconfiguration
      does not silence alerts for the full day.
    """
    if start_hour == end_hour:
        return False
    h = int(now_utc.hour)
    if start_hour < end_hour:
        return start_hour <= h < end_hour
    return h >= start_hour or h < end_hour
