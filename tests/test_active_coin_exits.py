"""Regression tests for active coin exit metadata."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase
from config.settings import settings


def test_exit_listed_on_honors_runtime_target_exchanges(tmp_path, monkeypatch):
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    db.add_coin(
        {
            "symbol": "ZAP",
            "name": "Zap",
            "slug": "zap",
            "gains": {"7d": 12.0, "30d": 45.0},
            "uniformity_score": 82.0,
            "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "12345"},
        }
    )

    _entered, exited, _blocked = db.get_entered_exited([])

    assert len(exited) == 1
    assert exited[0]["symbol"] == "ZAP"
    assert exited[0]["listed_on"] == ["mexc"]
