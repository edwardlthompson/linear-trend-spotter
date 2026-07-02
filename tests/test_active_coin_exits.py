"""Tests for active coin exit metadata."""

from __future__ import annotations

from config.settings import settings
from database.models import ActiveCoinsDatabase


def test_exit_listed_on_uses_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "scanner.db")
    try:
        db.add_coin(
            {
                "symbol": "ABC",
                "name": "Example Coin",
                "slug": "abc",
                "gains": {"7d": 10.0, "30d": 40.0},
                "uniformity_score": 75.0,
                "exchange_volumes": {
                    "coinbase": "N/A",
                    "kraken": "N/A",
                    "mexc": "12345.0",
                },
            }
        )

        _entered, exited, _blocked = db.get_entered_exited([], cooldown_hours=0)

        assert len(exited) == 1
        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
