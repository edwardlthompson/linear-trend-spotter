"""Regression tests for active-coin exit metadata."""

from __future__ import annotations

from database import models as db_models
from database.models import ActiveCoinsDatabase


def test_exit_listed_on_uses_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(db_models.settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "scanner.db")
    try:
        db.add_coin(
            {
                "symbol": "ABC",
                "name": "Alpha Beta",
                "gecko_id": "alpha-beta",
                "slug": "alpha-beta",
                "gains": {"7d": 10.0, "30d": 40.0},
                "uniformity_score": 80.0,
                "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "123456"},
                "current_price": 1.25,
            }
        )

        entered, exited, blocked = db.get_entered_exited([], cooldown_hours=6)

        assert entered == []
        assert blocked == []
        assert [row["symbol"] for row in exited] == ["ABC"]
        assert exited[0]["listed_on"] == ["mexc"]
        assert db.get_active() == {}
    finally:
        db.close()
