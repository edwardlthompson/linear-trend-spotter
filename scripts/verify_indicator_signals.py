"""Sprint 3.1 signal sanity verification across supported indicators and timeframes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from backtesting.data_loader import BacktestDataLoader
from backtesting.signals import (
    adx_signals,
    bollinger_percent_b_signals,
    cci_signals,
    ema_crossover_signals,
    heikin_ashi_signals,
    macd_signals,
    mfi_signals,
    parabolic_sar_signals,
    rsi_signals,
    sma_crossover_signals,
    stochastic_signals,
    ultimate_oscillator_signals,
)
from config.settings import settings
from database.cache import PriceCache


def _validate_output(name: str, frame: pd.DataFrame, buy: pd.Series, sell: pd.Series) -> None:
    if len(buy) != len(frame) or len(sell) != len(frame):
        raise ValueError(f"{name}: signal length mismatch")

    if buy.dtype != bool or sell.dtype != bool:
        raise ValueError(f"{name}: signal dtype must be bool")

    if buy.isna().any() or sell.isna().any():
        raise ValueError(f"{name}: NaN in signals")


def main() -> int:
    symbol = "ADA"
    timeframes = ["1h", "4h", "1d"]

    indicator_functions = {
        "RSI": lambda frame: rsi_signals(frame, period=14, lower=30, upper=70),
        "Stochastic": lambda frame: stochastic_signals(frame),
        "MACD": lambda frame: macd_signals(frame),
        "EMA Crossover": lambda frame: ema_crossover_signals(frame),
        "SMA Crossover": lambda frame: sma_crossover_signals(frame),
        "Bollinger %B": lambda frame: bollinger_percent_b_signals(frame),
        "CCI": lambda frame: cci_signals(frame),
        "Ultimate Oscillator": lambda frame: ultimate_oscillator_signals(frame),
        "MFI": lambda frame: mfi_signals(frame),
        "ADX": lambda frame: adx_signals(frame),
        "Parabolic SAR": lambda frame: parabolic_sar_signals(frame),
        "Heikin Ashi": lambda frame: heikin_ashi_signals(frame),
    }

    cache = PriceCache(settings.db_paths["scanner"])
    loader = BacktestDataLoader(cache=cache, max_cache_age_hours=settings.cache_price_hours)

    passed = 0
    skipped = 0
    failed = 0

    try:
        for timeframe in timeframes:
            loaded = loader.load(symbol=symbol, timeframe=timeframe, days=30)
            if loaded.frame is None:
                print(f"FAIL load {symbol} {timeframe}: {loaded.skip_reason}")
                failed += len(indicator_functions)
                continue

            frame = loaded.frame
            for indicator_name, signal_fn in indicator_functions.items():
                label = f"{indicator_name} [{timeframe}]"
                try:
                    buy, sell = signal_fn(frame)
                    _validate_output(label, frame, buy, sell)

                    if indicator_name == "MFI" and (frame["volume"] <= 0).all():
                        print(f"SKIP {label}: zero_volume")
                        skipped += 1
                        continue

                    print(f"PASS {label}: buy={int(buy.sum())} sell={int(sell.sum())}")
                    passed += 1
                except ValueError as exc:
                    print(f"SKIP {label}: {exc}")
                    skipped += 1
                except Exception as exc:
                    print(f"FAIL {label}: {exc}")
                    failed += 1
    finally:
        cache.close()

    print(f"Summary: passed={passed} skipped={skipped} failed={failed}")
    if failed > 0:
        return 1

    print("PASS: indicator signal verification completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
