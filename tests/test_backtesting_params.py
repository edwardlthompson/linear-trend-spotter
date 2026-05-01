"""Milestone P2: injected backtest params; lazy settings in defaults."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_params_module_import_avoids_eager_settings() -> None:
    sys.modules.pop("config.settings", None)
    sys.modules.pop("backtesting.params", None)
    importlib.import_module("backtesting.params")
    assert "config.settings" not in sys.modules


def test_subprocess_params_import_avoids_eager_settings() -> None:
    root = Path(__file__).resolve().parent.parent
    code = (
        "import sys\n"
        "assert 'config.settings' not in sys.modules\n"
        "import backtesting.params\n"
        "assert 'config.settings' not in sys.modules\n"
    )
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(root),
        check=True,
    )


def test_loader_respects_injected_ohlcv_thresholds() -> None:
    pytest.importorskip("pandas")
    from backtesting.data_loader import BacktestDataLoader
    from backtesting.params import BacktestLoaderParams

    lp = BacktestLoaderParams(
        coingecko_calls_per_minute=10,
        cmc_api_key="",
        ohlcv_min_1h_bars_per_day=24,
        ohlcv_min_1h_bars_slack=12,
        ohlcv_min_1h_bars_floor=600,
        ohlcv_min_1d_bars_slack=2,
        ohlcv_min_1d_bars_floor=25,
    )
    loader = BacktestDataLoader(MagicMock(), max_cache_age_hours=1, loader_params=lp)
    assert loader._hourly_min_bars_threshold(30) == max(24 * 30 - 12, 600)
    assert loader._daily_min_bars_threshold(30) == max(30 - 2, 25)
