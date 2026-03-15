"""Verifier for backtest OHLCV completeness and resampling integrity.

Default mode is strict.
Use bounded sanity mode for quick, deterministic checks under API rate limits:

    python scripts/verify_backtest_data.py --sanity
"""

from __future__ import annotations

import sqlite3
import sys
import time
import argparse
import multiprocessing as mp
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.coingecko_mapper import CoinGeckoMapper
from backtesting.data_loader import BacktestDataLoader
from config.settings import settings
from database.cache import PriceCache


def get_verifier_scope() -> tuple[list[str], str]:
    if settings.backtest_require_target_exchange:
        exchanges = [str(exchange).strip().lower() for exchange in settings.backtest_exchanges if str(exchange).strip()]
        if exchanges:
            return exchanges, f"backtest target exchanges ({', '.join(exchanges)})"

    exchanges = [str(exchange).strip().lower() for exchange in settings.target_exchanges if str(exchange).strip()]
    return exchanges, f"scanner target exchanges ({', '.join(exchanges)})"


def get_scope_symbols(db_path: Path, exchanges: list[str], limit: int = 10) -> list[str]:
    if not db_path.exists():
        return []

    if not exchanges:
        return []

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        placeholders = ",".join(["?" for _ in exchanges])
        cursor.execute(
            f"""
            SELECT DISTINCT symbol
            FROM exchange_listings
            WHERE exchange IN ({placeholders})
            ORDER BY symbol ASC
            LIMIT ?
            """,
            (*exchanges, limit),
        )
        return [str(row[0]).upper() for row in cursor.fetchall()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify backtest OHLCV data completeness for the configured exchange scope"
    )
    parser.add_argument(
        "--sanity",
        action="store_true",
        help="Run bounded quick-check mode (3 symbols, max 60s, require 1 pass).",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=12,
        help="Max in-scope symbols to check (default: 12).",
    )
    parser.add_argument(
        "--min-passed",
        type=int,
        default=10,
        help="Minimum PASS symbols required for success (default: 10).",
    )
    parser.add_argument(
        "--min-symbols-found",
        type=int,
        default=10,
        help="Minimum in-scope symbols required in exchange DB before run starts (default: 10).",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=0.0,
        help="Hard runtime cap in seconds (0 disables cap).",
    )
    parser.add_argument(
        "--per-symbol-timeout",
        type=float,
        default=0.0,
        help="Per-symbol hard timeout in seconds via subprocess isolation (0 disables).",
    )
    return parser.parse_args()


def resolve_gecko_ids(symbols: list[str]) -> dict[str, str]:
    aliases = settings.coingecko_id_aliases
    unresolved = [symbol for symbol in symbols if symbol not in aliases]

    resolved: dict[str, str] = {
        symbol: aliases[symbol]
        for symbol in symbols
        if symbol in aliases
    }

    if not unresolved:
        return resolved

    mapper = CoinGeckoMapper(settings.db_paths["mappings"])
    try:
        resolved.update(mapper.get_coin_ids_batch(unresolved))
    finally:
        mapper.close()

    return resolved


def _verify_symbol(
    symbol: str,
    gecko_id: str | None,
    scanner_db_path: str,
    max_cache_age_hours: int,
) -> tuple[str, str]:
    cache = PriceCache(Path(scanner_db_path))
    loader = BacktestDataLoader(cache=cache, max_cache_age_hours=max_cache_age_hours)

    try:
        result_1h = loader.load(symbol=symbol, timeframe="1h", days=30, gecko_id=gecko_id)
        if result_1h.frame is None:
            return "SKIP", f"{symbol}: {result_1h.skip_reason}"

        result_4h = loader.load(symbol=symbol, timeframe="4h", days=30, gecko_id=gecko_id)
        result_1d = loader.load(symbol=symbol, timeframe="1d", days=30, gecko_id=gecko_id)
        if result_4h.frame is None or result_1d.frame is None:
            reason = result_4h.skip_reason or result_1d.skip_reason
            return "SKIP", f"{symbol}: resample_failure:{reason}"

        if len(result_1h.frame) < 600:
            return "SKIP", f"{symbol}: insufficient_1h_points:{len(result_1h.frame)}"

        return (
            "PASS",
            (
                f"{symbol}: 1h={len(result_1h.frame)} 4h={len(result_4h.frame)} "
                f"1d={len(result_1d.frame)} source={result_1h.source}"
            ),
        )
    finally:
        cache.close()


def _symbol_worker(
    symbol: str,
    gecko_id: str | None,
    scanner_db_path: str,
    max_cache_age_hours: int,
    queue: mp.Queue,
) -> None:
    try:
        status, detail = _verify_symbol(symbol, gecko_id, scanner_db_path, max_cache_age_hours)
        queue.put((status, detail))
    except Exception as exc:
        queue.put(("SKIP", f"{symbol}: worker_error:{exc}"))


def main() -> int:
    args = parse_args()

    max_symbols = int(args.max_symbols)
    min_passed = int(args.min_passed)
    min_symbols_found = int(args.min_symbols_found)
    max_seconds = float(args.max_seconds)
    per_symbol_timeout = float(args.per_symbol_timeout)

    if args.sanity:
        max_symbols = min(max_symbols, 3)
        min_passed = min(min_passed, 1)
        min_symbols_found = min(min_symbols_found, 1)
        if max_seconds <= 0:
            max_seconds = 60.0
        if per_symbol_timeout <= 0:
            per_symbol_timeout = 20.0

    if max_symbols <= 0:
        print("FAIL: --max-symbols must be > 0")
        return 1
    if min_passed < 0:
        print("FAIL: --min-passed must be >= 0")
        return 1
    if min_symbols_found < 0:
        print("FAIL: --min-symbols-found must be >= 0")
        return 1
    if max_seconds < 0:
        print("FAIL: --max-seconds must be >= 0")
        return 1
    if per_symbol_timeout < 0:
        print("FAIL: --per-symbol-timeout must be >= 0")
        return 1

    scope_exchanges, scope_label = get_verifier_scope()
    candidate_limit = max(max_symbols, min_symbols_found) * 20
    candidate_symbols = get_scope_symbols(settings.db_paths["exchanges"], scope_exchanges, limit=candidate_limit)
    if len(candidate_symbols) < min_symbols_found:
        print(f"FAIL: fewer than {min_symbols_found} symbols found for {scope_label} in exchanges.db")
        return 1

    resolved_candidate_ids = resolve_gecko_ids(candidate_symbols)
    symbols = [symbol for symbol in candidate_symbols if symbol in resolved_candidate_ids]
    symbols.extend(symbol for symbol in candidate_symbols if symbol not in resolved_candidate_ids)
    symbols = symbols[:max_symbols]

    gecko_ids = {symbol: resolved_candidate_ids[symbol] for symbol in symbols if symbol in resolved_candidate_ids}

    passed = 0
    checked = 0
    timed_out = False
    start = time.monotonic()

    scanner_db_path = str(settings.db_paths["scanner"])

    for symbol in symbols:
        gecko_id = gecko_ids.get(symbol)
        if max_seconds > 0 and (time.monotonic() - start) >= max_seconds:
            timed_out = True
            print(f"STOP: runtime cap reached ({max_seconds:.1f}s); ending early")
            break

        checked += 1

        if per_symbol_timeout > 0:
            result_queue: mp.Queue = mp.Queue()
            process = mp.Process(
                target=_symbol_worker,
                args=(symbol, gecko_id, scanner_db_path, settings.cache_price_hours, result_queue),
            )
            process.start()
            process.join(per_symbol_timeout)

            if process.is_alive():
                process.terminate()
                process.join()
                print(f"SKIP {symbol}: per_symbol_timeout:{per_symbol_timeout:.1f}s")
                continue

            if result_queue.empty():
                print(f"SKIP {symbol}: worker_no_result")
                continue

            status, detail = result_queue.get()
        else:
            status, detail = _verify_symbol(symbol, gecko_id, scanner_db_path, settings.cache_price_hours)

        if status == "PASS":
            passed += 1
            print(f"PASS {detail}")
        else:
            print(f"SKIP {detail}")

    elapsed = time.monotonic() - start
    print(
        f"Summary: scope={scope_label}, checked={checked}, passed={passed}, required>={min_passed}, "
        f"symbols_limit={max_symbols}, elapsed={elapsed:.1f}s, timed_out={timed_out}"
    )
    if passed < min_passed:
        print(f"FAIL: verifier requires at least {min_passed} symbols with valid OHLCV for {scope_label}")
        return 1

    print("PASS: OHLCV verifier succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
