"""Regression tests for active-coin exit metadata."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase


def _active_coin() -> dict:
    return {
        "symbol": "ABC",
        "name": "ABC Coin",
        "gecko_id": "abc-coin",
        "slug": "abc-coin",
        "gains": {"7d": 10.0, "30d": 40.0},
        "uniformity_score": 80.0,
        "exchange_volumes": {
            "coinbase": "N/A",
            "kraken": "N/A",
            "mexc": "1234567",
        },
    }


def test_exit_listed_on_uses_runtime_target_exchanges(tmp_path) -> None:
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(_active_coin())

        _entered, exited, _blocked = db.get_entered_exited([], target_exchanges=("mexc",))

        assert [row["symbol"] for row in exited] == ["ABC"]
        assert exited[0]["listed_on"] == ["mexc"]
    finally:
        db.close()
