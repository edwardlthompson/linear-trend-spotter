"""Active coin exit regression coverage."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase
from config.settings import settings


def test_exit_listed_on_uses_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(
            {
                "symbol": "ZAP",
                "name": "Zap",
                "gecko_id": "zap",
                "slug": "zap",
                "gains": {"7d": 12, "30d": 45},
                "uniformity_score": 70,
                "current_price": 1.0,
                "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "1200000"},
            }
        )

        _entered, exited, _blocked = db.get_entered_exited([])

        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
