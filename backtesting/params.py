"""Constructor-injected limits for backtesting (Milestone P2).

Hosts that embed only `backtesting/` can build `BacktestLoaderParams` /
`BacktestRunnerParams` without importing the scanner `settings` singleton.
`loader_params_from_settings` / `runner_params_from_settings` map the current
`config.settings` for the integrated worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BacktestLoaderParams:
    """API + OHLCV gate knobs for `BacktestDataLoader`."""

    coingecko_calls_per_minute: int
    cmc_api_key: str
    ohlcv_min_1h_bars_per_day: int
    ohlcv_min_1h_bars_slack: int
    ohlcv_min_1h_bars_floor: int
    ohlcv_min_1d_bars_slack: int
    ohlcv_min_1d_bars_floor: int


def loader_params_from_settings() -> BacktestLoaderParams:
    from config.settings import settings

    return BacktestLoaderParams(
        coingecko_calls_per_minute=int(settings.coingecko_calls_per_minute),
        cmc_api_key=str(settings.cmc_api_key or ""),
        ohlcv_min_1h_bars_per_day=int(settings.ohlcv_min_1h_bars_per_day),
        ohlcv_min_1h_bars_slack=int(settings.ohlcv_min_1h_bars_slack),
        ohlcv_min_1h_bars_floor=int(settings.ohlcv_min_1h_bars_floor),
        ohlcv_min_1d_bars_slack=int(settings.ohlcv_min_1d_bars_slack),
        ohlcv_min_1d_bars_floor=int(settings.ohlcv_min_1d_bars_floor),
    )


@dataclass(frozen=True, slots=True)
class BacktestRunnerParams:
    """Orchestration + worker pool inputs for `run_backtests_for_final_results`."""

    loader: BacktestLoaderParams
    backtest_exchanges: tuple[str, ...]
    backtest_require_target_exchange: bool
    backtest_max_coins_per_run: int
    base_dir: Path
    backtest_checkpoint_file: Path
    backtest_telemetry_file: Path
    backtest_timeframes: tuple[str, ...]
    backtest_indicators: tuple[str, ...]
    backtest_trailing_stop_min: int
    backtest_trailing_stop_max: int
    backtest_trailing_stop_step: int
    backtest_failure_samples_limit: int
    backtest_enabled: bool
    backtest_resume_enabled: bool
    backtest_parallel_workers: int
    backtest_max_param_combos: int
    scanner_db_path: str
    cache_price_hours: int
    backtest_starting_capital: float
    backtest_fee_bps_round_trip: float
    backtest_per_coin_timeout_seconds: int


def runner_params_from_settings() -> BacktestRunnerParams:
    from config.settings import settings

    ex = settings.backtest_exchanges
    if not isinstance(ex, list):
        exchanges: tuple[str, ...] = ()
    else:
        exchanges = tuple(str(x).strip().lower() for x in ex if str(x).strip())

    tf = settings.backtest_timeframes
    if isinstance(tf, list) and tf:
        timeframes = tuple(str(x).lower() for x in tf)
    else:
        timeframes = ("1h", "4h", "1d")

    ind = settings.backtest_indicators
    if isinstance(ind, list):
        indicators = tuple(str(x).strip() for x in ind if str(x).strip())
    else:
        indicators = ()

    return BacktestRunnerParams(
        loader=loader_params_from_settings(),
        backtest_exchanges=exchanges,
        backtest_require_target_exchange=bool(settings.backtest_require_target_exchange),
        backtest_max_coins_per_run=int(settings.backtest_max_coins_per_run),
        base_dir=Path(settings.base_dir),
        backtest_checkpoint_file=Path(settings.backtest_checkpoint_file),
        backtest_telemetry_file=Path(settings.backtest_telemetry_file),
        backtest_timeframes=timeframes,
        backtest_indicators=indicators,
        backtest_trailing_stop_min=int(settings.backtest_trailing_stop_min),
        backtest_trailing_stop_max=int(settings.backtest_trailing_stop_max),
        backtest_trailing_stop_step=int(settings.backtest_trailing_stop_step),
        backtest_failure_samples_limit=int(settings.backtest_failure_samples_limit),
        backtest_enabled=bool(settings.backtest_enabled),
        backtest_resume_enabled=bool(settings.backtest_resume_enabled),
        backtest_parallel_workers=int(settings.backtest_parallel_workers),
        backtest_max_param_combos=int(settings.backtest_max_param_combos),
        scanner_db_path=str(settings.db_paths["scanner"]),
        cache_price_hours=int(settings.cache_price_hours),
        backtest_starting_capital=float(settings.backtest_starting_capital),
        backtest_fee_bps_round_trip=float(settings.backtest_fee_bps_round_trip),
        backtest_per_coin_timeout_seconds=int(settings.backtest_per_coin_timeout_seconds),
    )
