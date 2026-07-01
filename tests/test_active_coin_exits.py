from pathlib import Path

from config.settings import settings
from database.models import ActiveCoinsDatabase


def test_exit_listing_inference_honors_runtime_target_exchanges(tmp_path: Path) -> None:
    original_target_exchanges = list(settings._config.get("TARGET_EXCHANGES", []))
    settings._config["TARGET_EXCHANGES"] = ["coinbase", "kraken", "mexc"]
    try:
        active_db = ActiveCoinsDatabase(tmp_path / "active.db")
        active_db.add_coin(
            {
                "symbol": "ZAP",
                "name": "Zap",
                "gecko_id": "zap",
                "slug": "zap",
                "gains": {"7d": 12.0, "30d": 40.0},
                "uniformity_score": 80,
                "exchange_volumes": {
                    "coinbase": "N/A",
                    "kraken": "N/A",
                    "mexc": "2.5M",
                },
                "current_price": 1.23,
            }
        )

        _entered, exited, _blocked = active_db.get_entered_exited([])
    finally:
        settings._config["TARGET_EXCHANGES"] = original_target_exchanges

    assert len(exited) == 1
    assert exited[0]["symbol"] == "ZAP"
    assert exited[0]["listed_on"] == ["mexc"]
