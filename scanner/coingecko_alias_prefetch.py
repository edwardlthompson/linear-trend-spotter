"""Prefetch CoinGecko markets rows for configured ID aliases — Milestone I2."""

from __future__ import annotations

from typing import Any


def prefetch_alias_markets_by_gecko_id(
    *,
    top_coins_provider: str,
    coingecko_id_aliases: dict[str, str],
    all_symbols: list[str],
    gecko: Any,
    app_logger: Any,
) -> dict[str, dict]:
    """Bulk-fetch /coins/markets rows for symbols that use CoinGecko ID aliases."""
    alias_markets_by_id: dict[str, dict] = {}
    if top_coins_provider != "coingecko" or not coingecko_id_aliases:
        return alias_markets_by_id

    prefetch_ids = sorted(
        {
            str(coingecko_id_aliases[str(sym or "").strip().upper()]).strip().lower()
            for sym in all_symbols
            if str(sym or "").strip().upper() in coingecko_id_aliases
        }
    )
    if prefetch_ids:
        alias_markets_by_id = gecko.get_markets_rows_for_ids(prefetch_ids)
        if alias_markets_by_id:
            app_logger.info(
                "📦 Prefetched CoinGecko /coins/markets for %s id-alias row(s)",
                len(alias_markets_by_id),
            )
    return alias_markets_by_id
