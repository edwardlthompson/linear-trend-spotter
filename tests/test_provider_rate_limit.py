"""provider_rate_limit helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from utils.provider_rate_limit import MinIntervalGate, backoff_seconds_for_attempt


def test_min_interval_gate_instantiates() -> None:
    g = MinIntervalGate(60)
    g.wait()
    g.wait()


def test_backoff_honors_retry_after_header() -> None:
    resp = MagicMock()
    resp.headers = {"Retry-After": "42"}
    assert backoff_seconds_for_attempt(0, response=resp, max_backoff=120) == 42.0


def test_backoff_exponential_without_header() -> None:
    s = backoff_seconds_for_attempt(2, response=None, max_backoff=1000)
    assert s >= 15 * (2**2)

