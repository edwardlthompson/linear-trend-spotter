"""Sprint 3.2 verifier for optimizer bounds and trailing-stop sweep."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.optimizer import optimize_indicator


def make_synthetic_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=240, freq="1h", tz="UTC")
    base = 100.0
    closes = [base + i * 0.05 + ((i % 12) - 6) * 0.12 for i in range(len(index))]

    frame = pd.DataFrame(
        {
            "open": [value - 0.15 for value in closes],
            "high": [value + 0.45 for value in closes],
            "low": [value - 0.55 for value in closes],
            "close": closes,
            "volume": [1000 + (i % 24) * 40 for i in range(len(index))],
        },
        index=index,
    )
    return frame


def main() -> int:
    timeframe = "1h"
    max_combos = 50
    frame = make_synthetic_frame()

    indicators = ["RSI", "MACD", "Heikin Ashi"]
    passed_with_best = 0
    skipped_no_best = 0

    for indicator in indicators:
        summary = optimize_indicator(
            frame=frame,
            indicator=indicator,
            timeframe=timeframe,
            max_param_combos=max_combos,
            starting_capital=1000.0,
            fee_bps_round_trip=52.0,
        )

        if summary.combos_evaluated > max_combos:
            print(f"FAIL {indicator}: combo cap violated ({summary.combos_evaluated} > {max_combos})")
            return 1

        expected_stops = 10  # 2, 4, 6, 8, 10, 12, 14, 16, 18, 20
        if summary.stops_tested != expected_stops:
            print(f"FAIL {indicator}: stop sweep expected {expected_stops} got {summary.stops_tested}")
            return 1

        if summary.best_result is None:
            skipped_no_best += 1
            print(
                f"SKIP {indicator}: no qualifying result (win% filter={50.0:.1f}+) "
                f"after combos={summary.combos_evaluated}, runs={summary.total_runs}"
            )
            continue

        best_stop = summary.best_result.get(
            "trailing_stop_loss_pct",
            summary.best_result.get("trailing_stop_pct"),
        )
        if best_stop is None or not (2.0 <= float(best_stop) <= 20.0):
            print(f"FAIL {indicator}: invalid trailing stop in best result")
            return 1

        if "params" not in summary.best_result:
            print(f"FAIL {indicator}: missing params in best result")
            return 1

        print(
            f"PASS {indicator}: combos={summary.combos_evaluated}, runs={summary.total_runs}, "
            f"best_net={summary.best_result['net_pct']:.2f}%, stop={float(best_stop):.0f}%"
        )
        passed_with_best += 1

    if passed_with_best == 0:
        print(
            "FAIL: no indicators produced qualifying best_result; "
            "cannot verify trailing-stop fields"
        )
        return 1

    print(
        f"PASS: optimizer bounds verification completed "
        f"(passed={passed_with_best}, skipped_no_best={skipped_no_best})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
