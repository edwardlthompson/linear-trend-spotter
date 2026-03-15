"""Sprint 2.2 standalone backtest runner (RSI/EMA/SMA + B&H)."""

from __future__ import annotations

import argparse
from pathlib import Path

from backtesting.data_loader import BacktestDataLoader
from backtesting.engine import compute_buy_and_hold, run_backtest
from backtesting.models import BacktestConfig
from backtesting.report import render_ranked_table
from backtesting.signals import ema_crossover_signals, rsi_signals, sma_crossover_signals
from config.settings import settings
from database.cache import PriceCache


def _format_money(value: float) -> str:
    return f"${value:,.2f}"


def _format_pct(value: float) -> str:
    return f"{value:.2f}%"


def _run_for_timeframe(symbol: str, timeframe: str, loader: BacktestDataLoader, config: BacktestConfig) -> list[dict]:
    load_result = loader.load(symbol=symbol, timeframe=timeframe, days=30)
    if load_result.frame is None:
        raise RuntimeError(f"Data load failed for {symbol} {timeframe}: {load_result.skip_reason}")

    frame = load_result.frame

    rows: list[dict] = []

    strategy_specs = [
        {
            "name": "RSI",
            "settings": "period=14, buy<30, sell>70",
            "signal_fn": lambda f: rsi_signals(f, period=14, lower=30, upper=70),
        },
        {
            "name": "EMA Crossover",
            "settings": "short=12, long=26",
            "signal_fn": lambda f: ema_crossover_signals(f, short_period=12, long_period=26),
        },
        {
            "name": "SMA Crossover",
            "settings": "short=20, long=50",
            "signal_fn": lambda f: sma_crossover_signals(f, short_period=20, long_period=50),
        },
    ]

    for spec in strategy_specs:
        buy_signals, sell_signals = spec["signal_fn"](frame)
        result = run_backtest(frame=frame, buy_signals=buy_signals, sell_signals=sell_signals, config=config)

        rows.append(
            {
                "Indicator": spec["name"],
                "TF": timeframe,
                "Key Settings": spec["settings"],
                "Stop Loss %": _format_pct(config.trailing_stop_pct),
                "Final $": _format_money(result.final_equity),
                "Net %": _format_pct(result.net_pct),
                "Trades": result.total_trades,
                "Win %": _format_pct(result.win_pct),
                "_net_value": float(result.net_pct),
                "_final_value": float(result.final_equity),
            }
        )

    buy_hold = compute_buy_and_hold(frame, config)
    rows.append(
        {
            "Indicator": "B&H",
            "TF": timeframe,
            "Key Settings": "buy first close, sell last close",
            "Stop Loss %": "-",
            "Final $": _format_money(buy_hold.final_equity),
            "Net %": _format_pct(buy_hold.net_pct),
            "Trades": "-",
            "Win %": "-",
            "_net_value": float(buy_hold.net_pct),
            "_final_value": float(buy_hold.final_equity),
        }
    )

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sprint 2.2 starter backtests")
    parser.add_argument("--symbol", default="ADA", help="Symbol to backtest (default: ADA)")
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["1h,4h,1d"],
        help="Timeframes from {1h,4h,1d}. Accepts comma-separated and/or space-separated values.",
    )
    parser.add_argument("--trailing-stop", type=float, default=5.0, help="Trailing stop percent (default: 5)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    requested_timeframes = []
    for token in args.timeframes:
        requested_timeframes.extend([item.strip().lower() for item in str(token).split(",") if item.strip()])

    alias_map = {
        "daily": "1d",
        "d": "1d",
        "1": "1d",
    }
    requested_timeframes = [alias_map.get(item, item) for item in requested_timeframes]
    allowed_timeframes = {"1h", "4h", "1d"}
    invalid = [item for item in requested_timeframes if item not in allowed_timeframes]
    if invalid:
        raise ValueError(f"Unsupported timeframe(s): {invalid}")
    if float(args.trailing_stop) < 1.0:
        raise ValueError("--trailing-stop must be >= 1.0")

    config = BacktestConfig(
        starting_capital=settings.backtest_starting_capital,
        fee_bps_round_trip=settings.backtest_fee_bps_round_trip,
        trailing_stop_loss_pct=args.trailing_stop,
    )

    cache = PriceCache(settings.db_paths["scanner"])

    try:
        loader = BacktestDataLoader(cache=cache, max_cache_age_hours=settings.cache_price_hours)

        all_rows: list[dict] = []
        for timeframe in requested_timeframes:
            all_rows.extend(_run_for_timeframe(args.symbol.upper(), timeframe, loader, config))

        output = render_ranked_table(all_rows)
        print(output)
        return 0
    finally:
        cache.close()


if __name__ == "__main__":
    raise SystemExit(main())
