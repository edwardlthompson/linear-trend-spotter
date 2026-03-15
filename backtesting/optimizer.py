"""Hill-climbing coordinate-descent optimizer with TSL-only sweep.

Replaces the exhaustive Cartesian grid search.  For each indicator the search
starts from the midpoint of every parameter's candidate list (the "default"
value) and then iteratively explores one-step neighbors in each dimension,
moving to whichever neighbor produces the best improvement.  The search
converges when no neighbor beats the current position or the max_param_combos
visit budget is exhausted.

TP and TTP are no longer swept; only TSL is varied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .engine import run_backtest
from .models import BacktestConfig
from .parameter_space import PARAMETER_SPACE
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


def trailing_stop_values(min_stop: int = 2, max_stop: int = 20, step: int = 2) -> list[int]:
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


def _params_key(params: dict[str, Any]) -> tuple:
    """Hashable representation of a parameter dict."""
    return tuple(sorted(params.items()))


def optimize_indicator(
    frame: pd.DataFrame,
    indicator: str,
    timeframe: str,
    max_param_combos: int = 100,
    starting_capital: float = 1000.0,
    fee_bps_round_trip: float = 52.0,
    trailing_stop_min: int = 2,
    trailing_stop_max: int = 20,
    trailing_stop_step: int = 2,
) -> OptimizationSummary:
    """Coordinate-descent hill-climbing optimizer — TSL only, no TP/TTP.

    max_param_combos caps the total number of unique parameter sets visited
    (the node budget for the hill-climb graph), not a Cartesian product size.
    """
    if max_param_combos <= 0:
        raise ValueError("max_param_combos must be > 0")

    space = PARAMETER_SPACE.get(indicator, {})
    stop_values = trailing_stop_values(trailing_stop_min, trailing_stop_max, trailing_stop_step)

    evaluated: list[dict] = []
    total_runs = 0
    visited: set[tuple] = set()
    signal_cache: dict[tuple[int, bytes, bytes], dict | None] = {}

    def _best_for_params(params: dict[str, Any]) -> dict | None:
        """Run TSL sweep for fixed params; return row with best net_pct or None."""
        nonlocal total_runs
        try:
            buy_signals, sell_signals = generate_indicator_signals(indicator, frame, params)
        except Exception:
            return None

        fp = _signal_fingerprint(buy_signals, sell_signals)
        if fp in signal_cache:
            cached = signal_cache[fp]
            if cached is not None:
                row = dict(cached)
                row["params"] = params
                return row
            return None

        best: dict | None = None
        for stop_pct in stop_values:
            total_runs += 1
            cfg = BacktestConfig(
                starting_capital=starting_capital,
                fee_bps_round_trip=fee_bps_round_trip,
                trailing_stop_loss_pct=float(stop_pct),
                take_profit_pct=0.0,
                trailing_take_profit_pct=0.0,
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
                "take_profit_pct": 0.0,
                "trailing_take_profit_pct": 0.0,
                "final_equity": float(result.final_equity),
                "net_pct": float(result.net_pct),
                "trades": int(result.total_trades),
                "tsl_hits": sum(1 for t in result.trades if t.exit_reason == "trailing_stop_loss"),
                "win_pct": float(result.win_pct),
            }
            if float(row["win_pct"]) > MIN_STRATEGY_WIN_PCT:
                if best is None or row["net_pct"] > best["net_pct"]:
                    best = row

        signal_cache[fp] = dict(best) if best else None
        return best

    # ------------------------------------------------------------------ #
    # Heikin Ashi (and any future zero-parameter indicators)              #
    # ------------------------------------------------------------------ #
    if not space:
        result = _best_for_params({})
        if result:
            evaluated.append(result)
        return OptimizationSummary(
            indicator=indicator,
            timeframe=timeframe,
            combos_evaluated=1,
            stops_tested=len(stop_values),
            total_runs=total_runs,
            skipped_combos=0,
            best_result=select_best_result(evaluated),
        )

    # ------------------------------------------------------------------ #
    # Hill-climbing: start from midpoint of each parameter list           #
    # ------------------------------------------------------------------ #
    current_params: dict[str, Any] = {
        key: vals[len(vals) // 2] for key, vals in space.items()
    }
    combos_evaluated = 0

    pk = _params_key(current_params)
    visited.add(pk)
    combos_evaluated += 1
    current_result = _best_for_params(current_params)
    if current_result:
        evaluated.append(current_result)

    improved = True
    while improved and combos_evaluated < max_param_combos:
        improved = False
        best_neighbor_result: dict | None = None
        best_neighbor_params: dict | None = None

        # Evaluate all one-step neighbors across every dimension.
        # Pick the single globally best neighbor in this pass.
        for param_key, candidates in space.items():
            try:
                current_idx = candidates.index(current_params[param_key])
            except ValueError:
                continue

            for delta in (-1, 1):
                neighbor_idx = current_idx + delta
                if not (0 <= neighbor_idx < len(candidates)):
                    continue

                trial_params = dict(current_params)
                trial_params[param_key] = candidates[neighbor_idx]
                trial_key = _params_key(trial_params)
                if trial_key in visited:
                    continue

                visited.add(trial_key)
                combos_evaluated += 1

                trial_result = _best_for_params(trial_params)
                if trial_result:
                    evaluated.append(trial_result)

                current_score = current_result["net_pct"] if current_result else float("-inf")
                trial_score = trial_result["net_pct"] if trial_result else float("-inf")

                if trial_score > current_score:
                    if (
                        best_neighbor_result is None
                        or trial_score > best_neighbor_result["net_pct"]
                    ):
                        best_neighbor_result = trial_result
                        best_neighbor_params = trial_params

                if combos_evaluated >= max_param_combos:
                    break
            if combos_evaluated >= max_param_combos:
                break

        if best_neighbor_params is not None:
            current_params = best_neighbor_params
            current_result = best_neighbor_result
            improved = True

    return OptimizationSummary(
        indicator=indicator,
        timeframe=timeframe,
        combos_evaluated=combos_evaluated,
        stops_tested=len(stop_values),
        total_runs=total_runs,
        skipped_combos=0,
        best_result=select_best_result(evaluated),
    )
