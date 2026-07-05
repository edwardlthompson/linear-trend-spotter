from __future__ import annotations

from config.settings import settings
from database.models import ActiveCoinsDatabase


def test_exit_listing_inference_honors_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(
            {
                "symbol": "XYZ",
                "name": "Example",
                "gains": {"7d": 10.0, "30d": 40.0},
                "uniformity_score": 70.0,
                "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "$1,234,567"},
                "slug": "example",
                "current_price": 1.0,
            }
        )

        _entered, exited, _blocked = db.get_entered_exited([])

        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
