"""Regression tests for active-coin exit payload metadata."""

from database.models import ActiveCoinsDatabase
from scanner.web_push_notify import _coin_push_row
from config.settings import settings


def test_exit_listed_on_honors_runtime_target_exchanges(tmp_path, monkeypatch):
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    db.add_coin(
        {
            "symbol": "MX",
            "name": "Mexc Only",
            "gecko_id": "mexc-only",
            "gains": {"7d": 10.0, "30d": 35.0},
            "uniformity_score": 80,
            "exchange_volumes": {
                "coinbase": "N/A",
                "kraken": "N/A",
                "mexc": "$2.5M",
            },
            "slug": "mexc-only",
            "current_price": 1.23,
        },
    )

    _entered, exited, _blocked = db.get_entered_exited([])

    assert len(exited) == 1
    assert exited[0]["listed_on"] == ["mexc"]
    assert _coin_push_row(exited[0]) == {
        "symbol": "MX",
        "listed_on": ["mexc"],
    }
