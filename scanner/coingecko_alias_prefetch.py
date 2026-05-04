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
    """Bulk-fetch ``/coins/markets`` rows for CoinGecko ID aliases (chunked, ≤250 ids/request).

    Bundles **all** alias targets from ``COINGECKO_ID_ALIASES`` plus any ids referenced by
    exchange-listed symbols—one batched path instead of per-symbol ``/coins/{id}`` calls later.
    """
    alias_markets_by_id: dict[str, dict] = {}
    if top_coins_provider != "coingecko" or not coingecko_id_aliases:
        return alias_markets_by_id

    from_config: set[str] = set()
    for raw_val in coingecko_id_aliases.values():
        cid = str(raw_val or "").strip().lower()
        if cid:
            from_config.add(cid)

    from_exchange_listings: set[str] = set()
    for sym in all_symbols:
        key = str(sym or "").strip().upper()
        if key in coingecko_id_aliases:
            cid = str(coingecko_id_aliases[key] or "").strip().lower()
            if cid:
                from_exchange_listings.add(cid)

    prefetch_ids = sorted(from_config | from_exchange_listings)
    if prefetch_ids:
        alias_markets_by_id = gecko.get_markets_rows_for_ids(prefetch_ids)
        if alias_markets_by_id:
            app_logger.info(
                "📦 Prefetched CoinGecko /coins/markets for %s alias id(s) "
                "(%s from config, %s from listings∩aliases; chunked bulk)",
                len(alias_markets_by_id),
                len(from_config),
                len(from_exchange_listings),
            )
    return alias_markets_by_id


def top_up_alias_markets_for_symbols(
    *,
    top_coins_provider: str,
    coingecko_id_aliases: dict[str, str],
    all_symbols: list[str],
    alias_markets_by_id: dict[str, dict],
    gecko: Any,
    app_logger: Any,
) -> None:
    """Second bulk pass when the first ``/coins/markets`` response omitted some ids (rare).

    Mutates ``alias_markets_by_id`` in place. No extra HTTP when nothing is missing.
    """
    if top_coins_provider != "coingecko" or not coingecko_id_aliases:
        return
    missing: set[str] = set()
    for sym in all_symbols:
        su = str(sym or "").strip().upper()
        if su not in coingecko_id_aliases:
            continue
        gid = str(coingecko_id_aliases[su] or "").strip().lower()
        if gid and gid not in alias_markets_by_id:
            missing.add(gid)
    if not missing:
        return
    extra = gecko.get_markets_rows_for_ids(sorted(missing))
    if extra:
        alias_markets_by_id.update(extra)
        app_logger.info(
            "📦 CoinGecko alias markets top-up: %s id(s) merged after first batch miss",
            len(extra),
        )
