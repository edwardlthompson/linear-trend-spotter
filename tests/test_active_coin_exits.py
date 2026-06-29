from database.models import ActiveCoinsDatabase
from database import models


def test_exit_listed_on_uses_runtime_target_exchanges(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(models.settings._config, "TARGET_EXCHANGES", ["mexc"])
    db = ActiveCoinsDatabase(str(tmp_path / "active.db"))
    db.add_coin(
        {
            "symbol": "MX",
            "name": "MEXC Only",
            "gecko_id": "mexc-only",
            "slug": "mexc-only",
            "gains": {"7d": 12, "30d": 40},
            "uniformity_score": 80,
            "exchange_volumes": {
                "coinbase": "N/A",
                "kraken": "N/A",
                "mexc": "$1,000,000",
            },
        }
    )

    _entered, exited, _blocked = db.get_entered_exited([])

    assert [row["symbol"] for row in exited] == ["MX"]
    assert exited[0]["listed_on"] == ["mexc"]
