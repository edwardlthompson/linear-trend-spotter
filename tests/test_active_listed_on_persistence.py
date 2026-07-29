"""Exit listed_on must survive when exchange volumes are all N/A."""

from __future__ import annotations

from pathlib import Path

from database.models import ActiveCoinsDatabase
from push_server.notify_filtering import coin_matches_notify_exchanges


def _coin(
    *,
    symbol: str = "SOL",
    listed_on: list[str] | None = None,
    volumes: dict[str, str] | None = None,
) -> dict:
    return {
        "symbol": symbol,
        "name": "Solana",
        "gecko_id": "solana",
        "slug": "solana",
        "gains": {"7d": 12.0, "30d": 40.0},
        "uniformity_score": 80.0,
        "listed_on": listed_on if listed_on is not None else ["kraken"],
        "exchange_volumes": volumes
        if volumes is not None
        else {"coinbase": "N/A", "kraken": "N/A", "mexc": "N/A"},
        "current_price": 100.0,
    }


def test_exit_keeps_persisted_listed_on_when_volumes_are_na(tmp_path: Path) -> None:
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(_coin(listed_on=["kraken"], volumes={"coinbase": "N/A", "kraken": "N/A", "mexc": "N/A"}))
        active = db.get_active()
        assert active["SOL"]["listed_on"] == ["kraken"]

        _entered, exited, _blocked = db.get_entered_exited([])
        assert len(exited) == 1
        assert exited[0]["listed_on"] == ["kraken"]
        assert coin_matches_notify_exchanges(exited[0], ["kraken"])
    finally:
        db.close()


def test_update_preserves_listed_on_when_new_row_omits_it(tmp_path: Path) -> None:
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(_coin(listed_on=["coinbase", "kraken"]))
        db.update_coin(
            _coin(
                listed_on=[],
                volumes={"coinbase": "N/A", "kraken": "1.5M", "mexc": "N/A"},
            )
        )
        assert db.get_active()["SOL"]["listed_on"] == ["coinbase", "kraken"]

        _entered, exited, _blocked = db.get_entered_exited([])
        assert exited[0]["listed_on"] == ["coinbase", "kraken"]
    finally:
        db.close()


def test_volume_fallback_still_used_without_persisted_listed_on(tmp_path: Path) -> None:
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.add_coin(
            _coin(
                listed_on=[],
                volumes={"coinbase": "N/A", "kraken": "2.0", "mexc": "N/A"},
            )
        )
        # Legacy rows / empty listed_on still infer from non-N/A volumes.
        db.execute("UPDATE active_coins SET listed_on = NULL WHERE coin_symbol = ?", ("SOL",))
        _entered, exited, _blocked = db.get_entered_exited([])
        assert exited[0]["listed_on"] == ["kraken"]
    finally:
        db.close()
