"""Sprint 2.1 deterministic verifier for core backtesting engine."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.engine import compute_buy_and_hold, run_backtest
from backtesting.models import BacktestConfig


def make_synthetic_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=12, freq="1h", tz="UTC")
    closes = [100, 103, 107, 111, 108, 104, 106, 110, 115, 112, 109, 113]

    frame = pd.DataFrame(
        {
            "open": closes,
            "high": [value + 1.0 for value in closes],
            "low": [value - 1.5 for value in closes],
            "close": closes,
            "volume": [1000 + i * 10 for i in range(len(closes))],
        },
        index=index,
    )
    return frame


def make_signals(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    buy = pd.Series(False, index=frame.index)
    sell = pd.Series(False, index=frame.index)

    buy.iloc[1] = True
    buy.iloc[6] = True
    sell.iloc[9] = True
    return buy, sell


def approx_equal(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def main() -> int:
    frame = make_synthetic_frame()
    buy_signals, sell_signals = make_signals(frame)

    config = BacktestConfig(
        starting_capital=1000.0,
        fee_bps_round_trip=52.0,
        trailing_stop_loss_pct=5.0,
    )

    result_first = run_backtest(frame, buy_signals, sell_signals, config)
    result_second = run_backtest(frame, buy_signals, sell_signals, config)

    if result_first.total_trades <= 0:
        print("FAIL: expected at least one trade")
        return 1

    if not approx_equal(result_first.final_equity, result_second.final_equity):
        print("FAIL: final_equity not deterministic")
        return 1

    if not approx_equal(result_first.net_pct, result_second.net_pct):
        print("FAIL: net_pct not deterministic")
        return 1

    if result_first.total_trades != result_second.total_trades:
        print("FAIL: total_trades not deterministic")
        return 1

    if not (0.0 <= result_first.win_pct <= 100.0):
        print("FAIL: invalid win_pct range")
        return 1

    buy_hold = compute_buy_and_hold(frame, config)
    if buy_hold.final_equity <= 0:
        print("FAIL: buy-and-hold produced non-positive final equity")
        return 1

    print("PASS: deterministic engine verification succeeded")
    print(
        f"Engine -> final=${result_first.final_equity:.2f}, net={result_first.net_pct:.2f}%, "
        f"trades={result_first.total_trades}, win%={result_first.win_pct:.2f}"
    )
    print(f"B&H    -> final=${buy_hold.final_equity:.2f}, net={buy_hold.net_pct:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
