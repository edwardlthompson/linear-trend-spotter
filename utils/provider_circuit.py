"""Lightweight consecutive-failure circuit for HTTP providers (optional, non-fatal)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

_logger = logging.getLogger(__name__)


class ProviderCallCircuit:
    """Open after N consecutive failures; half-open after recovery timeout (seconds)."""

    __slots__ = ("_lock", "name", "threshold", "recovery_s", "failures", "opened_at", "degraded_logged")

    def __init__(self, name: str, *, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self.name = str(name or "provider")
        self.threshold = max(1, int(failure_threshold))
        self.recovery_s = max(1.0, float(recovery_timeout))
        self._lock = threading.Lock()
        self.failures = 0
        self.opened_at = 0.0
        self.degraded_logged = False

    def allow(self) -> bool:
        with self._lock:
            if self.failures < self.threshold:
                return True
            if time.time() - self.opened_at >= self.recovery_s:
                if not self.degraded_logged:
                    _logger.info("Provider circuit %s half-open (trial request)", self.name)
                    self.degraded_logged = True
                return True
            if not self.degraded_logged:
                _logger.warning(
                    "Provider circuit %s OPEN — skipping requests for ~%.0fs (degraded mode)",
                    self.name,
                    self.recovery_s,
                )
                self.degraded_logged = True
            return False

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.degraded_logged = False

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.time()


def circuit_from_settings(settings: Any, name: str) -> ProviderCallCircuit | None:
    """Build a circuit from ``settings.circuit_failure_threshold`` and ``circuit_recovery_timeout``."""
    try:
        th = int(settings.circuit_failure_threshold)
        rec = float(settings.circuit_recovery_timeout)
    except Exception:
        return None
    return ProviderCallCircuit(name, failure_threshold=th, recovery_timeout=rec)
