"""Exchange listing symbol universe (STEP 2) — Milestone I2 pipeline extraction."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def load_exchange_symbol_universe(
    exchange_db_path: Path,
    exchange_db: Any,
    ExchangeFetcher: type,
    app_logger: Any,
    target_exchanges: tuple[str, ...] | None = None,
) -> tuple[list[str], set[str]]:
    """Return distinct symbols from exchange_listings for target exchanges only."""
    if target_exchanges is None:
        from config.settings import settings

        target_exchanges = tuple(settings.target_exchanges)
    active = tuple(str(ex).strip().lower() for ex in target_exchanges if str(ex).strip())
    all_symbols: set[str] = set()

    def _load_symbols(conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        if active:
            placeholders = ",".join("?" * len(active))
            cursor.execute(
                f"SELECT DISTINCT symbol FROM exchange_listings WHERE exchange IN ({placeholders})",
                active,
            )
        else:
            cursor.execute("SELECT DISTINCT symbol FROM exchange_listings")
        for row in cursor.fetchall():
            all_symbols.add(row[0])

    if exchange_db_path.exists():
        try:
            conn = sqlite3.connect(exchange_db_path)
            _load_symbols(conn)
            conn.close()
            app_logger.info(
                f"   ✓ Found {len(all_symbols)} unique symbols across {', '.join(active) or 'all exchanges'}"
            )
        except Exception as e:
            app_logger.warning(f"   Could not query exchange_listings: {e}")

    if not all_symbols:
        app_logger.warning("   No exchange data found. Attempting one-time exchange listings refresh...")
        try:
            ExchangeFetcher(exchange_db).update_all_exchanges(list(active))

            conn = sqlite3.connect(exchange_db_path)
            _load_symbols(conn)
            conn.close()

            if all_symbols:
                app_logger.info(f"   ✓ Exchange listings refreshed: {len(all_symbols)} symbols")
        except Exception as refresh_error:
            app_logger.warning(f"   Exchange listings refresh failed: {refresh_error}")

    used_minimal_fallback = False
    if not all_symbols:
        app_logger.warning("   No exchange data found after refresh - using default list")
        all_symbols = {"BTC", "ETH", "SOL", "XRP"}
        used_minimal_fallback = True

    sym_set = set(all_symbols)
    sym_list = list(all_symbols)
    if used_minimal_fallback:
        app_logger.error(
            "   EXCHANGE_UNIVERSE_FALLBACK: exchange_listings empty after refresh — "
            "scanning only %s symbols. Qualified dashboard output may look empty. "
            "If this persists after exchange refresh, check exchange_data logs (Windows: "
            "non-ASCII print() can abort refresh on cp1252 consoles).",
            sorted(sym_set),
        )
    app_logger.info(f"   ✓ Scanning ALL {len(sym_list)} coins from exchange listings")
    return sym_list, sym_set
