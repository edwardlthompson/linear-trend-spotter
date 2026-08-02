"""Regression: never inject stale disk backtest_results into entered coins."""

from __future__ import annotations

from scanner.backtest_entry_enrich import enrich_entered_with_current_backtest


def test_skips_enrichment_when_summary_missing() -> None:
    """J4 degrade / backtest failure leaves summary None — leave fields unset."""
    coin = {"symbol": "SOL", "name": "Solana"}
    entered = [coin]
    enrich_entered_with_current_backtest(entered, [coin], None)
    assert "backtest_top_strategies" not in coin
    assert "backtest_buy_hold" not in coin


def test_attaches_only_current_run_summary_rows() -> None:
    coin = {"symbol": "SOL", "name": "Solana"}
    entered = [coin]
    summary = {
        "results": [
            {
                "symbol": "SOL",
                "indicator": "EMA",
                "timeframe": "1h",
                "net_pct": 12.5,
                "params": {"fast": 8, "slow": 21},
            },
            {
                "symbol": "SOL",
                "indicator": "B&H",
                "timeframe": "1h",
                "net_pct": 4.0,
                "params": {},
            },
            {
                "symbol": "ETH",
                "indicator": "EMA",
                "timeframe": "1h",
                "net_pct": 99.0,
                "params": {},
            },
        ]
    }
    enrich_entered_with_current_backtest(entered, [coin], summary)
    strategies = coin.get("backtest_top_strategies") or []
    assert strategies and strategies[0]["indicator"] == "EMA"
    assert strategies[0]["net_pct"] == 12.5
    assert coin["backtest_buy_hold"]["net_pct"] == 4.0
    assert all(str(row.get("symbol", "")).upper() == "SOL" for row in strategies)


def test_does_not_overwrite_existing_strategy_fields() -> None:
    coin = {
        "symbol": "BTC",
        "backtest_top_strategies": [{"indicator": "RSI", "net_pct": 1.0}],
        "backtest_buy_hold": {"indicator": "B&H", "net_pct": 2.0},
    }
    summary = {
        "results": [
            {"symbol": "BTC", "indicator": "EMA", "timeframe": "1h", "net_pct": 50.0, "params": {}},
            {"symbol": "BTC", "indicator": "B&H", "timeframe": "1h", "net_pct": 3.0, "params": {}},
        ]
    }
    enrich_entered_with_current_backtest([coin], [coin], summary)
    assert coin["backtest_top_strategies"][0]["indicator"] == "RSI"
    assert coin["backtest_buy_hold"]["net_pct"] == 2.0


def test_main_no_longer_loads_disk_backtest_artifact() -> None:
    """Guard against reintroducing the stale-artifact path in main.py."""
    from pathlib import Path

    main_src = Path(__file__).resolve().parents[1] / "main.py"
    text = main_src.read_text(encoding="utf-8")
    assert "enrich_entered_with_current_backtest" in text
    assert "Could not read backtest artifact for notifications" not in text
    assert "fallback_summary" not in text
    # Disk artifact may still be written by the runner; main must not read it back.
    assert 'artifact_path = settings.base_dir / "backtest_results.json"' not in text
