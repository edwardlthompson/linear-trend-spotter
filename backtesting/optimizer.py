"""Constrained parameter and trailing-stop optimizer for Sprint 3.2."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .engine import run_backtest
from .models import BacktestConfig
from .parameter_space import generate_parameter_combinations
from .selection import select_best_result
from .signals import generate_indicator_signals


@dataclass
class OptimizationSummary:
    indicator: str
    timeframe: str
    combos_evaluated: int
    stops_tested: int
    total_runs: int
    skipped_combos: int
    best_result: dict | None


def trailing_stop_values(min_stop: int = 0, max_stop: int = 20, step: int = 1) -> list[int]:
    if step <= 0:
        raise ValueError("step must be > 0")
    if min_stop < 0 or max_stop < min_stop:
        raise ValueError("invalid stop range")
    return list(range(min_stop, max_stop + 1, step))


def optimize_indicator(
    frame: pd.DataFrame,
    indicator: str,
    timeframe: str,
    max_param_combos: int = 100,
    starting_capital: float = 1000.0,
    fee_bps_round_trip: float = 52.0,
) -> OptimizationSummary:
    if max_param_combos <= 0:
        raise ValueError("max_param_combos must be > 0")

    param_combos = generate_parameter_combinations(indicator, max_combos=max_param_combos)
    stop_values = trailing_stop_values(0, 20, 1)

    evaluated = []
    skipped_combos = 0
    total_runs = 0

    for params in param_combos:
        try:
            buy_signals, sell_signals = generate_indicator_signals(indicator, frame, params)
        except Exception:
            skipped_combos += 1
            continue

        best_for_combo = None
        for stop_pct in stop_values:
            total_runs += 1
            cfg = BacktestConfig(
                starting_capital=starting_capital,
                fee_bps_round_trip=fee_bps_round_trip,
                trailing_stop_pct=float(stop_pct),
            )

            result = run_backtest(
                frame=frame,
                buy_signals=buy_signals,
                sell_signals=sell_signals,
                config=cfg,
            )

            row = {
                "indicator": indicator,
                "timeframe": timeframe,
                "params": params,
                "trailing_stop_pct": float(stop_pct),
                "final_equity": float(result.final_equity),
                "net_pct": float(result.net_pct),
                "trades": int(result.total_trades),
                "win_pct": float(result.win_pct),
            }

            if best_for_combo is None or row["net_pct"] > best_for_combo["net_pct"]:
                best_for_combo = row

        if best_for_combo is not None:
            evaluated.append(best_for_combo)

    best = select_best_result(evaluated)

    return OptimizationSummary(
        indicator=indicator,
        timeframe=timeframe,
        combos_evaluated=len(param_combos),
        stops_tested=len(stop_values),
        total_runs=total_runs,
        skipped_combos=skipped_combos,
        best_result=best,
    )
