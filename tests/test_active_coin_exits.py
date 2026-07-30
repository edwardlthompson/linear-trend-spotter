"""Regression coverage for active-coin exit payloads."""

from database.models import ActiveCoinsDatabase
from push_server.notify_filtering import filter_events_for_subscriber
from config.settings import settings


def test_exit_listed_on_honors_runtime_target_exchanges(tmp_path, monkeypatch):
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])
    db = ActiveCoinsDatabase(tmp_path / "active.db")

    db.add_coin(
        {
            "symbol": "ZAP",
            "name": "Zap Token",
            "gecko_id": "zap-token",
            "gains": {"7d": 12.0, "30d": 45.0},
            "uniformity_score": 72,
            "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "2100000"},
            "slug": "zap-token",
            "current_price": 1.25,
        }
    )

    _entered, exited, _blocked = db.get_entered_exited([])

    assert len(exited) == 1
    assert exited[0]["listed_on"] == ["mexc"]
    _entered_filtered, exited_filtered = filter_events_for_subscriber(["mexc"], [], exited)
    assert exited_filtered == exited
