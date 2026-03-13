"""Sprint 3.2 verifier for optimizer bounds and trailing-stop sweep."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.data_loader import BacktestDataLoader
from backtesting.optimizer import optimize_indicator
from config.settings import settings
from database.cache import PriceCache


def main() -> int:
    symbol = "ADA"
    timeframe = "1h"
    max_combos = 50

    cache = PriceCache(settings.db_paths["scanner"])
    loader = BacktestDataLoader(cache=cache, max_cache_age_hours=settings.cache_price_hours)

    try:
        loaded = loader.load(symbol=symbol, timeframe=timeframe, days=30)
        if loaded.frame is None:
            print(f"FAIL: data load failed: {loaded.skip_reason}")
            return 1

        frame = loaded.frame
        indicators = ["RSI", "MACD", "Heikin Ashi"]

        for indicator in indicators:
            summary = optimize_indicator(
                frame=frame,
                indicator=indicator,
                timeframe=timeframe,
                max_param_combos=max_combos,
                starting_capital=settings.backtest_starting_capital,
                fee_bps_round_trip=settings.backtest_fee_bps_round_trip,
            )

            if summary.combos_evaluated > max_combos:
                print(
                    f"FAIL {indicator}: combo cap violated ({summary.combos_evaluated} > {max_combos})"
                )
                return 1

            if summary.stops_tested != 20:
                print(f"FAIL {indicator}: stop sweep expected 20 got {summary.stops_tested}")
                return 1

            if summary.best_result is None:
                print(f"FAIL {indicator}: best_result missing")
                return 1

            if not (1.0 <= summary.best_result["trailing_stop_pct"] <= 20.0):
                print(f"FAIL {indicator}: invalid trailing_stop_pct in best result")
                return 1

            if "params" not in summary.best_result:
                print(f"FAIL {indicator}: missing params in best result")
                return 1

            print(
                f"PASS {indicator}: combos={summary.combos_evaluated}, runs={summary.total_runs}, "
                f"best_net={summary.best_result['net_pct']:.2f}%, stop={summary.best_result['trailing_stop_pct']:.0f}%"
            )

        print("PASS: optimizer bounds verification completed")
        return 0
    finally:
        cache.close()


if __name__ == "__main__":
    raise SystemExit(main())
