"""Public qualified snapshot payload shape."""

from __future__ import annotations

from utils.scan_artifacts import build_public_qualified_snapshot


def test_full_field_set_includes_scan_interval_and_backtest() -> None:
    rows = [
        {
            "symbol": "ada",
            "name": "Cardano",
            "slug": "cardano",
            "gains": {"7d": 1.0, "30d": 2.0},
            "uniformity_score": 50.0,
            "health_score": 60,
            "backtest_top_strategies": [{"rank": 1}],
            "backtest_buy_hold": {"return_pct": 1.2},
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=1800)
    assert payload["scan_interval_seconds"] == 1800
    assert payload["coins"][0]["backtest_top_strategies"] == [{"rank": 1}]
    assert payload["coins"][0]["backtest_buy_hold"] == {"return_pct": 1.2}


def test_minimal_field_set_omits_backtest_and_exchange_fields() -> None:
    rows = [
        {
            "symbol": "ada",
            "name": "Cardano",
            "slug": "cardano",
            "gains": {"7d": 1.0, "30d": 2.0},
            "uniformity_score": 50.0,
            "health_score": 60,
            "backtest_top_strategies": [{"rank": 1}],
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="minimal", scan_interval_seconds=3600)
    coin = payload["coins"][0]
    assert "backtest_top_strategies" not in coin
    assert "exchange_volumes" not in coin
