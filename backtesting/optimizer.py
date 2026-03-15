"""Constrained parameter and trailing-stop optimizer for Sprint 3.2."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .engine import run_backtest
from .models import BacktestConfig
from .parameter_space import generate_parameter_combinations
from .selection import select_best_result
from .signals import generate_indicator_signals


MIN_STRATEGY_WIN_PCT = 50.0


@dataclass
class OptimizationSummary:
    indicator: str
    timeframe: str
    combos_evaluated: int
    stops_tested: int
    total_runs: int
    skipped_combos: int
    best_result: dict | None


def trailing_stop_values(min_stop: int = 1, max_stop: int = 20, step: int = 1) -> list[int]:
    if step <= 0:
        raise ValueError("step must be > 0")
    if min_stop < 1 or max_stop < min_stop:
        raise ValueError("invalid stop range")
    return list(range(min_stop, max_stop + 1, step))


def _signal_fingerprint(buy_signals: pd.Series, sell_signals: pd.Series) -> tuple[int, bytes, bytes]:
    buy_array = buy_signals.to_numpy(dtype=bool)
    sell_array = sell_signals.to_numpy(dtype=bool)
    buy_bits = np.packbits(buy_array.astype(np.uint8)).tobytes()
    sell_bits = np.packbits(sell_array.astype(np.uint8)).tobytes()
    return len(buy_array), buy_bits, sell_bits


def optimize_indicator(
    frame: pd.DataFrame,
    indicator: str,
    timeframe: str,
    max_param_combos: int = 100,
    starting_capital: float = 1000.0,
    fee_bps_round_trip: float = 52.0,
    trailing_stop_min: int = 1,
    trailing_stop_max: int = 20,
    trailing_stop_step: int = 1,
) -> OptimizationSummary:
    if max_param_combos <= 0:
        raise ValueError("max_param_combos must be > 0")

    param_combos = generate_parameter_combinations(indicator, max_combos=max_param_combos)
    stop_values = trailing_stop_values(trailing_stop_min, trailing_stop_max, trailing_stop_step)

    evaluated = []
    skipped_combos = 0
    total_runs = 0
    signal_cache: dict[tuple[int, bytes, bytes], dict | None] = {}

    for params in param_combos:
        try:
            buy_signals, sell_signals = generate_indicator_signals(indicator, frame, params)
        except Exception:
            skipped_combos += 1
            continue

        cache_key = _signal_fingerprint(buy_signals, sell_signals)
        cached_template = signal_cache.get(cache_key)
        if cached_template is not None:
            best_for_combo = dict(cached_template)
            best_for_combo["params"] = params
            evaluated.append(best_for_combo)
            continue
        if cache_key in signal_cache and signal_cache[cache_key] is None:
            continue

        best_for_combo = None
        for stop_pct in stop_values:
            for tp_pct in [0.0, 5.0, 10.0]:
                for ttp_pct in ([0.0] if tp_pct == 0.0 else [1.0, 2.0]):
                    total_runs += 1
                    cfg = BacktestConfig(
                        starting_capital=starting_capital,
                        fee_bps_round_trip=fee_bps_round_trip,
                        trailing_stop_loss_pct=float(stop_pct),
                        take_profit_pct=float(tp_pct),
                        trailing_take_profit_pct=float(ttp_pct),
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
                        "trailing_stop_loss_pct": float(stop_pct),
                        "take_profit_pct": float(tp_pct),
                        "trailing_take_profit_pct": float(ttp_pct),
                        "final_equity": float(result.final_equity),
                        "net_pct": float(result.net_pct),
                        "trades": int(result.total_trades),
                        "win_pct": float(result.win_pct),
                    }

                    if float(row["win_pct"]) > MIN_STRATEGY_WIN_PCT:
                        if best_for_combo is None or row["net_pct"] > best_for_combo["net_pct"]:
                            best_for_combo = row

        if best_for_combo is not None:
            signal_cache[cache_key] = dict(best_for_combo)
            evaluated.append(best_for_combo)
        else:
            signal_cache[cache_key] = None

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
