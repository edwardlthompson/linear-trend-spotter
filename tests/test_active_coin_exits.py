"""Active coin exit payload regressions."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase
from config.settings import settings


def test_exit_listed_on_honors_runtime_target_exchanges(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(
            {
                "symbol": "ALT",
                "name": "Altcoin",
                "gecko_id": "altcoin",
                "slug": "altcoin",
                "gains": {"7d": 10.0, "30d": 40.0},
                "uniformity_score": 70.0,
                "exchange_volumes": {
                    "coinbase": "N/A",
                    "kraken": "N/A",
                    "mexc": "12345",
                },
            }
        )

        _entered, exited, _blocked = db.get_entered_exited([])

        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
