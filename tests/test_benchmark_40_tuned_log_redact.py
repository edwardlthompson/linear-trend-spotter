"""Regression: benchmark progress log must not store secrets or raw addresses."""

from __future__ import annotations

import benchmark_40_tuned as b40


def test_redact_hex_address() -> None:
    msg = "tx 0x1234567890abcdef1234567890abcdef12345678"
    out = b40.redact_log_message(msg)
    assert "1234567890abcdef" not in out
    assert "REDACTED" in out


def test_redact_query_params() -> None:
    msg = "url https://x.y/z?apiKey=supersecret123&limit=1"
    out = b40.redact_log_message(msg)
    assert "supersecret123" not in out
    assert "apiKey=[REDACTED]" in out


def test_redact_bearer() -> None:
    msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.x"
    out = b40.redact_log_message(msg)
    assert "eyJ" not in out
    assert "Authorization: [REDACTED]" in out


def test_redact_cmc_header() -> None:
    msg = "X-CMC_PRO_API_KEY: abcde12345"
    out = b40.redact_log_message(msg)
    assert "abcde12345" not in out
    assert "X-CMC_PRO_API_KEY: [REDACTED]" in out


def test_redact_stray_bearer_token() -> None:
    msg = "using Bearer eyJhbGciOiJIUzI1NiJ9.notinheader"
    out = b40.redact_log_message(msg)
    assert "eyJ" not in out
    assert "Bearer [REDACTED]" in out


def test_passthrough_safe_line() -> None:
    msg = "maps_built coingecko=200 polygon=150"
    assert b40.redact_log_message(msg) == msg
