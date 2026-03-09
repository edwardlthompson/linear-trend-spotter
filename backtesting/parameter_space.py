"""Bounded parameter spaces for indicator optimization."""

from __future__ import annotations

from itertools import islice, product
from typing import Any

PARAMETER_SPACE: dict[str, dict[str, list[Any]]] = {
    "RSI": {
        "period": [10, 12, 14, 16, 18, 20],
        "lower": [20, 25, 30, 35, 40],
        "upper": [60, 65, 70, 75, 80],
    },
    "Stochastic": {
        "k_period": [10, 14, 18],
        "d_period": [3, 5],
        "smooth": [3, 5],
        "oversold": [15, 20, 25],
        "overbought": [75, 80, 85],
    },
    "MACD": {
        "fast_period": [8, 12, 16],
        "slow_period": [21, 26, 34],
        "signal_period": [7, 9, 12],
    },
    "EMA Crossover": {
        "short_period": [8, 12, 16, 20],
        "long_period": [26, 34, 50, 75],
    },
    "SMA Crossover": {
        "short_period": [10, 20, 30],
        "long_period": [50, 100, 150],
    },
    "Bollinger %B": {
        "period": [14, 20, 26],
        "std_dev": [1.5, 2.0, 2.5],
        "buy_threshold": [0.1, 0.2, 0.3],
        "sell_threshold": [0.7, 0.8, 0.9],
    },
    "CCI": {
        "period": [14, 20, 30],
        "oversold": [-150, -100, -75],
        "overbought": [75, 100, 150],
    },
    "Ultimate Oscillator": {
        "short_period": [5, 7, 10],
        "medium_period": [10, 14, 20],
        "long_period": [20, 28, 35],
        "oversold": [25, 30, 35],
        "overbought": [65, 70, 75],
    },
    "MFI": {
        "period": [10, 14, 20],
        "lower": [20, 25, 30],
        "upper": [70, 75, 80],
    },
    "ADX": {
        "period": [10, 14, 20],
        "adx_threshold": [15, 20, 25, 30],
        "di_diff_min": [1, 3, 5],
    },
    "Parabolic SAR": {
        "accel_step": [0.01, 0.02, 0.03],
        "max_step": [0.1, 0.2, 0.3],
    },
    "Heikin Ashi": {},
}


def generate_parameter_combinations(indicator: str, max_combos: int = 100) -> list[dict[str, Any]]:
    if indicator not in PARAMETER_SPACE:
        raise ValueError(f"Unknown indicator parameter space: {indicator}")

    space = PARAMETER_SPACE[indicator]
    if not space:
        return [{}]

    keys = list(space.keys())
    values = [space[key] for key in keys]

    combos = []
    for combo in islice(product(*values), max_combos):
        combos.append({key: value for key, value in zip(keys, combo)})

    return combos
