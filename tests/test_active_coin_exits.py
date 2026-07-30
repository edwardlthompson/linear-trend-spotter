"""Regression coverage for qualified-exit metadata."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase
from config.settings import settings


def test_exit_listed_on_honors_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(
            {
                "symbol": "ZAP",
                "name": "Zap",
                "gecko_id": "zap",
                "slug": "zap",
                "gains": {"7d": 10.0, "30d": 40.0},
                "uniformity_score": 80.0,
                "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "12345"},
                "current_price": 1.0,
            }
        )

        _entered, exited, _blocked = db.get_entered_exited([])

        assert exited[0]["symbol"] == "ZAP"
        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
