"""Regression: Active DB mutations must be deferrable until after notify."""

from __future__ import annotations

from pathlib import Path

from database.models import ActiveCoinsDatabase


def _coin(symbol: str, *, price: float = 10.0, gain_7d: float = 5.0, gain_30d: float = 12.0) -> dict:
    return {
        "symbol": symbol,
        "name": symbol.title(),
        "gecko_id": symbol.lower(),
        "slug": symbol.lower(),
        "current_price": price,
        "gains": {"7d": gain_7d, "30d": gain_30d},
        "uniformity_score": 80.0,
        "exchange_volumes": {"coinbase": "1000", "kraken": "N/A", "mexc": "N/A"},
    }


def test_get_entered_exited_apply_mutations_false_leaves_db_unchanged(tmp_path: Path):
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    db.add_coin(_coin("AAA", price=1.0))
    db.add_coin(_coin("BBB", price=2.0))

    entered, exited, blocked = db.get_entered_exited(
        [_coin("AAA", price=1.5), _coin("CCC", price=3.0)],
        cooldown_hours=6,
        apply_mutations=False,
    )

    assert {c["symbol"] for c in entered} == {"CCC"}
    assert {c["symbol"] for c in exited} == {"BBB"}
    assert blocked == []

    active = db.get_active()
    assert set(active.keys()) == {"AAA", "BBB"}
    assert "CCC" not in active
    assert db._get_cooldown_until("BBB") is None


def test_apply_after_diff_persists_enter_exit_and_stay_update(tmp_path: Path):
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    db.add_coin(_coin("AAA", price=1.0))
    db.add_coin(_coin("BBB", price=2.0))

    current = [_coin("AAA", price=1.5, gain_7d=9.0), _coin("CCC", price=3.0)]
    entered, exited, _blocked = db.get_entered_exited(
        current,
        cooldown_hours=6,
        apply_mutations=False,
    )
    for row in exited:
        row["exit_reason"] = "Uniformity score below threshold"

    db.apply_entered_exited_mutations(
        entered,
        exited,
        current,
        cooldown_hours=6,
    )

    active = db.get_active()
    assert set(active.keys()) == {"AAA", "CCC"}
    assert active["AAA"]["gain_7d"] == 9.0
    assert float(active["AAA"]["last_price"] or 0) == 1.5
    assert "BBB" not in active
    assert db._get_cooldown_until("BBB") is not None

    # Re-diff with same current set yields no churn once applied.
    entered2, exited2, _ = db.get_entered_exited(current, apply_mutations=False)
    assert entered2 == []
    assert exited2 == []


def test_default_apply_mutations_true_keeps_legacy_behavior(tmp_path: Path):
    db = ActiveCoinsDatabase(tmp_path / "active.db")
    db.add_coin(_coin("OLD", price=5.0))

    entered, exited, _ = db.get_entered_exited([_coin("NEW", price=7.0)], cooldown_hours=1)
    assert {c["symbol"] for c in entered} == {"NEW"}
    assert {c["symbol"] for c in exited} == {"OLD"}
    assert set(db.get_active().keys()) == {"NEW"}
    assert db._get_cooldown_until("OLD") is not None
