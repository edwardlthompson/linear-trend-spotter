"""Sprint 1.1 environment smoke test for backtesting stack."""

from __future__ import annotations

import sys


def main() -> int:
    checks = []

    try:
        import pandas as pd  # noqa: F401
        checks.append("pandas")
    except Exception as exc:
        print(f"FAIL: pandas import error: {exc}")
        return 1

    try:
        import numpy as np
        checks.append("numpy")
    except Exception as exc:
        print(f"FAIL: numpy import error: {exc}")
        return 1

    try:
        import vectorbt as vbt
        checks.append("vectorbt")
    except Exception as exc:
        print(f"FAIL: vectorbt import error: {exc}")
        return 1

    ta_lib_available = False
    try:
        import talib

        _ = talib.RSI(np.array([1.0, 1.1, 1.2, 1.3, 1.2, 1.25], dtype=float), timeperiod=3)
        ta_lib_available = True
        checks.append("TA-Lib")
    except Exception as exc:
        print(f"WARN: TA-Lib unavailable: {exc}")

    try:
        close = np.array([100, 101, 102, 101, 103, 105, 104, 106], dtype=float)
        entries = close > np.roll(close, 1)
        entries[0] = False
        exits = close < np.roll(close, 1)
        exits[0] = False

        portfolio = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            init_cash=1000.0,
            fees=0.0052 / 2,
            direction="longonly",
        )

        final_value = float(portfolio.value().iloc[-1])
        if final_value <= 0:
            print("FAIL: vectorbt smoke run produced non-positive final value")
            return 1

        checks.append("vectorbt-smoke-run")
    except Exception as exc:
        print(f"FAIL: vectorbt smoke run error: {exc}")
        return 1

    print("PASS: backtest environment smoke test")
    print(f"Checks passed: {', '.join(checks)}")
    print(f"TA-Lib status: {'available' if ta_lib_available else 'fallback-required'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
