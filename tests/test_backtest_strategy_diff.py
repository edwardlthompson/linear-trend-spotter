"""Tests for between-scan top-strategy fingerprint + diff line."""

import json
from pathlib import Path

from utils.backtest_strategy_diff import (
    build_event_summary_backtest_diff_line,
    describe_strategy_change,
    fingerprint_from_strategy_row,
    load_top_strategy_state,
    save_top_strategy_state,
)


def test_fingerprint_ignores_bh():
    assert fingerprint_from_strategy_row({"indicator": "B&H", "timeframe": "1d"}) is None


def test_describe_tsl_change():
    prev = {
        "indicator": "RSI",
        "timeframe": "4h",
        "params": {"length": 14},
        "tsl": 8.0,
        "tp": 0.0,
        "ttp": 0.0,
    }
    curr = {**prev, "tsl": 6.0}
    assert describe_strategy_change(prev, curr) == "tsl 8→6"


def test_build_event_summary_line_only_still_active():
    prev = {
        "ADA": {
            "indicator": "RSI",
            "timeframe": "4h",
            "params": {"length": 14},
            "tsl": 8.0,
            "tp": 0.0,
            "ttp": 0.0,
        }
    }
    final = [
        {
            "symbol": "ADA",
            "backtest_top_strategies": [
                {
                    "indicator": "RSI",
                    "timeframe": "4h",
                    "params": {"length": 14},
                    "trailing_stop_loss_pct": 6.0,
                    "take_profit_pct": 0.0,
                    "trailing_take_profit_pct": 0.0,
                }
            ],
        },
        {
            "symbol": "XRP",
            "backtest_top_strategies": [
                {
                    "indicator": "EMA",
                    "timeframe": "1h",
                    "params": {"fast": 10},
                    "trailing_stop_loss_pct": 4.0,
                    "take_profit_pct": 0.0,
                    "trailing_take_profit_pct": 0.0,
                }
            ],
        },
    ]
    line = build_event_summary_backtest_diff_line(
        previous_by_symbol=prev,
        final_results=final,
        still_qualified_symbols={"ADA"},
    )
    assert line is not None
    assert "ADA" in line
    assert "tsl 8→6" in line
    assert "XRP" not in line


def test_save_and_load_roundtrip(tmp_path: Path):
    final = [
        {
            "symbol": "SOL",
            "backtest_top_strategies": [
                {
                    "indicator": "RSI",
                    "timeframe": "1h",
                    "params": {"length": 21},
                    "trailing_stop_loss_pct": 10.0,
                    "take_profit_pct": 0.0,
                    "trailing_take_profit_pct": 0.0,
                }
            ],
        }
    ]
    p = tmp_path / "state.json"
    save_top_strategy_state(p, final)
    loaded = load_top_strategy_state(p)
    assert loaded["SOL"]["indicator"] == "RSI"
    assert loaded["SOL"]["params"]["length"] == 21
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw.get("version") == 1
    assert "by_symbol" in raw
