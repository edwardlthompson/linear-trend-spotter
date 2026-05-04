"""Thread-safe pacing for external HTTP APIs (CoinMarketCap, Polygon, etc.)."""

from __future__ import annotations

import random
import threading
import time


class MinIntervalGate:
    """Enforce at least ``60 / calls_per_minute`` seconds between consecutive ``wait()`` calls."""

    __slots__ = ("_lock", "_min_interval", "_last")

    def __init__(self, calls_per_minute: int) -> None:
        self._lock = threading.Lock()
        cpm = max(1, int(calls_per_minute))
        self._min_interval = 60.0 / float(cpm)
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last = time.time()


def backoff_seconds_for_attempt(
    attempt: int,
    *,
    response=None,
    max_backoff: float = 120.0,
    base_on_429: float = 15.0,
) -> float:
    """Compute sleep before retry. Honors ``Retry-After`` when present (429)."""
    if response is not None:
        ra = response.headers.get("Retry-After")
        if ra:
            try:
                sec = float(ra)
                if sec > 0:
                    return min(sec, max_backoff)
            except ValueError:
                pass
    # Exponential backoff with jitter (attempt is 0-based)
    base = min(base_on_429 * (2**attempt), max_backoff)
    return base + random.uniform(0, 2.0)
