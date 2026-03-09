"""Sprint 1.2 verifier for Kraken OHLCV completeness and resampling integrity."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.data_loader import BacktestDataLoader
from config.settings import settings
from database.cache import PriceCache


def get_kraken_symbols(db_path: Path, limit: int = 10) -> list[str]:
    if not db_path.exists():
        return []

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT symbol
            FROM exchange_listings
            WHERE exchange = 'kraken'
            ORDER BY symbol ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [str(row[0]).upper() for row in cursor.fetchall()]


def main() -> int:
    symbols = get_kraken_symbols(settings.db_paths["exchanges"], limit=12)
    if len(symbols) < 10:
        print("FAIL: fewer than 10 Kraken symbols found in exchanges.db")
        return 1

    cache = PriceCache(settings.db_paths["scanner"])
    loader = BacktestDataLoader(cache=cache, max_cache_age_hours=settings.cache_price_hours)

    passed = 0
    checked = 0

    try:
        for symbol in symbols:
            checked += 1
            result_1h = loader.load(symbol=symbol, timeframe="1h", days=30)
            if result_1h.frame is None:
                print(f"SKIP {symbol}: {result_1h.skip_reason}")
                continue

            result_4h = loader.load(symbol=symbol, timeframe="4h", days=30)
            result_1d = loader.load(symbol=symbol, timeframe="1d", days=30)
            if result_4h.frame is None or result_1d.frame is None:
                reason = result_4h.skip_reason or result_1d.skip_reason
                print(f"SKIP {symbol}: resample_failure:{reason}")
                continue

            if len(result_1h.frame) < 600:
                print(f"SKIP {symbol}: insufficient_1h_points:{len(result_1h.frame)}")
                continue

            passed += 1
            print(
                f"PASS {symbol}: 1h={len(result_1h.frame)} 4h={len(result_4h.frame)} 1d={len(result_1d.frame)} source={result_1h.source}"
            )

    finally:
        cache.close()

    print(f"Summary: checked={checked}, passed={passed}, required>=10")
    if passed < 10:
        print("FAIL: verifier requires at least 10 Kraken symbols with valid OHLCV")
        return 1

    print("PASS: OHLCV verifier succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
