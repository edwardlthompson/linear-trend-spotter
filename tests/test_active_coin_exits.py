"""Regression tests for active-coin exit payloads."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase
from config.settings import settings


def test_exit_listed_on_uses_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "scanner.db")
    try:
        db.add_coin(
            {
                "symbol": "ZAP",
                "name": "Zap",
                "slug": "zap",
                "gains": {"7d": 12.0, "30d": 40.0},
                "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "1234567"},
            }
        )

        _entered, exited, _blocked = db.get_entered_exited([])

        assert len(exited) == 1
        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
