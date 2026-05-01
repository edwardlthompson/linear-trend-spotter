"""Backtesting package.

Heavy submodules (``engine`` / ``pandas``) load only on attribute access so
``import backtesting`` does not pull ``pandas`` until you resolve e.g.
``backtesting.compute_buy_and_hold`` (P2).
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "compute_buy_and_hold",
    "run_backtest",
    "BacktestConfig",
    "BacktestDataLoader",
    "BacktestLoaderParams",
    "BacktestRunnerParams",
    "loader_params_from_settings",
    "runner_params_from_settings",
]


def __getattr__(name: str) -> Any:
    if name in ("compute_buy_and_hold", "run_backtest"):
        mod = importlib.import_module(".engine", __package__)
        return getattr(mod, name)
    if name == "BacktestConfig":
        mod = importlib.import_module(".models", __package__)
        return getattr(mod, name)
    if name == "BacktestDataLoader":
        mod = importlib.import_module(".data_loader", __package__)
        return getattr(mod, name)
    if name in (
        "BacktestLoaderParams",
        "BacktestRunnerParams",
        "loader_params_from_settings",
        "runner_params_from_settings",
    ):
        mod = importlib.import_module(".params", __package__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
