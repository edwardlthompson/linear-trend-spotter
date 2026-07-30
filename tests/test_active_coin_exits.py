"""Regression tests for active coin exit metadata."""

from __future__ import annotations

from config.settings import settings
from database.models import ActiveCoinsDatabase


def test_exit_listed_on_uses_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["mexc"])
    db = ActiveCoinsDatabase(tmp_path / "scanner.db")
    try:
        db.add_coin(
            {
                "symbol": "MEXC1",
                "name": "MEXC One",
                "gains": {"7d": 12.0, "30d": 45.0},
                "uniformity_score": 88.0,
                "exchange_volumes": {"mexc": "$2,000,000"},
                "slug": "mexc-one",
            }
        )

        entered, exited, blocked = db.get_entered_exited([])
    finally:
        db.close()

    assert entered == []
    assert blocked == []
    assert len(exited) == 1
    assert exited[0]["listed_on"] == ["mexc"]
