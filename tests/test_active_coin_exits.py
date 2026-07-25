"""Regression coverage for active-coin exit metadata."""

from __future__ import annotations

from config.settings import settings
from database.models import ActiveCoinsDatabase


def test_exit_listed_on_honors_runtime_target_exchanges(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(
            {
                "symbol": "ABC",
                "name": "ABC Token",
                "gecko_id": "abc-token",
                "slug": "abc-token",
                "gains": {"7d": 12.0, "30d": 45.0},
                "uniformity_score": 72.0,
                "exchange_volumes": {
                    "coinbase": "N/A",
                    "kraken": "N/A",
                    "mexc": "$1,234,567",
                },
            }
        )

        entered, exited, blocked = db.get_entered_exited([], cooldown_hours=0)

        assert entered == []
        assert blocked == []
        assert [coin["symbol"] for coin in exited] == ["ABC"]
        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
