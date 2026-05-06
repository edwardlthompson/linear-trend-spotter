from __future__ import annotations

from datetime import datetime, timezone

from utils.snapshot_validation import validate_public_snapshot


def test_validate_minimal_ok_payload() -> None:
    now = datetime.now(timezone.utc).isoformat()
    p = {
        "schema_version": 1,
        "updated_at": now,
        "coins": [{"symbol": "BTC", "name": "Bitcoin", "gains": {"7d": 1.0, "30d": 2.0}}],
        "scan_interval_seconds": 3600,
    }
    v = validate_public_snapshot(p)
    assert v["ok"] is True
    assert v["level"] == "ok"
    assert not v["issues"]


def test_validate_warns_on_empty_coins() -> None:
    now = datetime.now(timezone.utc).isoformat()
    p = {"schema_version": 1, "updated_at": now, "coins": []}
    v = validate_public_snapshot(p)
    assert v["stats"]["coin_count"] == 0
