"""Cooldown-blocked requalifiers must not remain in the public qualified set."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from database.models import ActiveCoinsDatabase
from scanner.exit_pipeline import exclude_cooldown_blocked_coins


def _qualified(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "name": f"{symbol} Coin",
        "gains": {"7d": 12.0, "30d": 40.0},
        "uniformity_score": 80,
        "exchange_volumes": {"coinbase": "1000", "kraken": "N/A", "mexc": "N/A"},
        "slug": symbol.lower(),
        "current_price": 1.25,
    }


def test_exclude_cooldown_blocked_coins_filters_symbols():
    coins = [_qualified("AAA"), _qualified("BBB"), _qualified("CCC")]
    blocked = [{"symbol": "bbb", "cooldown_until": "2099-01-01T00:00:00"}]
    kept = exclude_cooldown_blocked_coins(coins, blocked)
    assert [c["symbol"] for c in kept] == ["AAA", "CCC"]


def test_exclude_cooldown_blocked_coins_noop_when_empty():
    coins = [_qualified("AAA")]
    assert exclude_cooldown_blocked_coins(coins, []) is coins
    assert exclude_cooldown_blocked_coins([], [{"symbol": "AAA"}]) == []


def test_cooldown_requalifier_is_ghost_without_exclusion(tmp_path: Path):
    """Reproduce: cooldown blocks Active-DB entry but coin stays in final_results.

    Later drop therefore yields no worker exit — snapshot must drop the ghost.
    """
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    try:
        db.register_exit("GHOST", reason="prior exit", cooldown_hours=6)
        # Force cooldown into the future in case clock skew edges the boundary.
        future = (datetime.now() + timedelta(hours=6)).isoformat()
        db.execute(
            "UPDATE cooldown_exits SET cooldown_until_ts = ? WHERE coin_symbol = ?",
            (future, "GHOST"),
        )

        final_results = [_qualified("KEEP"), _qualified("GHOST")]
        entered, exited, blocked = db.get_entered_exited(final_results, cooldown_hours=6)

        assert entered and entered[0]["symbol"] == "KEEP"
        assert exited == []
        assert {b["symbol"] for b in blocked} == {"GHOST"}
        assert "GHOST" not in db.get_active()
        assert "KEEP" in db.get_active()

        # Without exclusion the public set still contains the ghost.
        assert any(c["symbol"] == "GHOST" for c in final_results)

        published = exclude_cooldown_blocked_coins(final_results, blocked)
        assert [c["symbol"] for c in published] == ["KEEP"]

        # Dropping the ghost later cannot emit a worker exit (never active).
        entered2, exited2, blocked2 = db.get_entered_exited(
            [_qualified("KEEP")], cooldown_hours=6
        )
        assert entered2 == []
        assert exited2 == []
        assert blocked2 == []
    finally:
        db.close()
