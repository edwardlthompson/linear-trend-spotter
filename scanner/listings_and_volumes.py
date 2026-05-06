"""Exchange listings, CoinGecko IDs, and per-exchange volumes (STEPS 4–6) — I2."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from api.coingecko import coingecko_ticker_exchange_ids_csv
from scanner.market_processing import process_tickers


def attach_target_exchange_listings(
    gain_qualified: list[dict[str, Any]],
    *,
    exchange_db: Any,
    target_exchanges: tuple[str, ...],
    app_logger: Any,
) -> None:
    """Populate each coin's listed_on from batch exchange listing checks."""
    app_logger.info("\n🏦 Getting exchange listing data...")

    symbols_for_listing_check = [
        str(coin.get("symbol", "")).upper() for coin in gain_qualified if coin.get("symbol")
    ]
    exchange_listing_maps: dict[str, dict[str, bool]] = {}
    for exchange in target_exchanges:
        exchange_listing_maps[exchange] = exchange_db.batch_check_listings(symbols_for_listing_check, exchange)

    for coin in gain_qualified:
        symbol = str(coin.get("symbol", "")).upper()
        coin["listed_on"] = [
            exchange for exchange in target_exchanges if exchange_listing_maps.get(exchange, {}).get(symbol, False)
        ]


def attach_coin_gecko_ids_and_learn(
    gain_qualified: list[dict[str, Any]],
    *,
    top_coins_provider: str,
    cg_mapper: Any,
    cmc_slug_resolver: Any,
    app_logger: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve CoinGecko IDs; teach slug resolver from CMC listing metadata when applicable."""
    app_logger.info(f"\n🔍 Getting CoinGecko IDs for {len(gain_qualified)} coins...")

    coins_with_cg_ids: list[dict[str, Any]] = []
    coins_without_cg_ids: list[str] = []

    for coin in gain_qualified:
        cg_id: str | None = None
        if top_coins_provider == "coingecko":
            pref = str(coin.get("slug") or "").strip().lower()
            if pref:
                cg_id = pref
        if not cg_id:
            name_hint = str(coin.get("name") or "").strip()
            cg_id = cg_mapper.get_coin_id_with_name_hint(
                coin["symbol"],
                name_hint if name_hint else None,
            )
        if not cg_id and coin.get("cmc_symbol"):
            cg_id = cg_mapper.get_coin_id_with_name_hint(
                str(coin["cmc_symbol"]),
                str(coin.get("name") or "").strip() or None,
            )
            if cg_id:
                app_logger.info(
                    f"   ↪️ {coin['symbol']}: CoinGecko ID resolved via CMC symbol {coin['cmc_symbol']}"
                )
        if cg_id:
            coin["cg_id"] = cg_id
            coin["gecko_id"] = cg_id
            coins_with_cg_ids.append(coin)
        else:
            coins_without_cg_ids.append(coin["symbol"])

    if cmc_slug_resolver:
        for coin in coins_with_cg_ids:
            gid = str(coin.get("gecko_id") or coin.get("cg_id") or "").strip().lower()
            cslug = str(coin.get("cmc_slug") or "").strip().lower()
            if not cslug and top_coins_provider == "cmc":
                raw = str(coin.get("slug") or "").strip().lower()
                if raw and raw != gid:
                    cslug = raw
            cid_raw = coin.get("cmc_id")
            cid: int | None = None
            if cid_raw is not None:
                try:
                    cid = int(cid_raw)
                except (TypeError, ValueError):
                    cid = None
            if gid and cslug and cslug != gid:
                cmc_slug_resolver.learn_from_cmc_listing_coin(
                    gecko_id=gid, cmc_slug=cslug, cmc_id=cid
                )
        cmc_slug_resolver.save_learned_if_dirty()

    app_logger.info(f"   Found CoinGecko IDs for {len(coins_with_cg_ids)} coins")
    return coins_with_cg_ids, coins_without_cg_ids


def hydrate_exchange_volumes_from_coingecko(
    coins_with_cg_ids: list[dict[str, Any]],
    *,
    cache: Any,
    gecko: Any,
    target_exchanges: tuple[str, ...],
    app_logger: Any,
) -> int:
    """Fetch or cache per-target-exchange volumes via CoinGecko tickers. Returns no-ticker coin count."""
    app_logger.info(f"\n💱 Fetching exchange volume data for {len(coins_with_cg_ids)} coins...")
    no_ticker_count = 0
    ticker_exchange_csv = coingecko_ticker_exchange_ids_csv(target_exchanges)

    by_gid: dict[str, list] = defaultdict(list)
    for i, coin in enumerate(coins_with_cg_ids, 1):
        app_logger.info(f"   [{i}/{len(coins_with_cg_ids)}] {coin['symbol']}")

        found_cached_volumes, cached_volumes = cache.get_exchange_volumes(coin["cg_id"])
        if found_cached_volumes and cached_volumes:
            coin["exchange_volumes"] = cached_volumes
            app_logger.info("      ✓ Using cached exchange volumes")
            continue

        gid_key = str(coin["cg_id"]).strip().lower()
        by_gid[gid_key].append(coin)

    for gid_key, group in by_gid.items():
        merged: list[dict[str, Any]] = []
        max_pages = 12
        for page in range(1, max_pages + 1):
            chunk = gecko.get_tickers(
                gid_key,
                exchange_ids=ticker_exchange_csv,
                page=page,
                order="volume_desc",
            )
            if not chunk or not isinstance(chunk.get("tickers"), list):
                break
            batch = chunk["tickers"]
            if not batch:
                break
            merged.extend(batch)
            if len(batch) < 100:
                break
        # If exchange_ids filter yields nothing (identifier mismatch upstream), fall back to one
        # unfiltered page sorted by volume so process_tickers can still pick target venues.
        if not merged:
            fb = gecko.get_tickers(gid_key, page=1, order="volume_desc")
            if fb and isinstance(fb.get("tickers"), list) and fb["tickers"]:
                merged = fb["tickers"][:400]
                app_logger.info(
                    "      ↪️ exchange_ids filter returned 0 ticker rows; using unfiltered page 1 "
                    "(trimmed to %s) for cg_id=%s",
                    len(merged),
                    gid_key,
                )
        tickers = {"tickers": merged} if merged else None
        if tickers:
            volumes = process_tickers(tickers, target_exchanges)
            for c in group:
                c["exchange_volumes"] = volumes
                cache.cache_exchange_volumes(c["cg_id"], volumes)
            app_logger.info(
                "      ✓ Got exchange volumes for %s coin(s) (cg_id=%s)",
                len(group),
                gid_key,
            )
        else:
            na_vols = {ex: "N/A" for ex in target_exchanges}
            for c in group:
                c["exchange_volumes"] = na_vols
            app_logger.info(
                "      ⚠️ No ticker data for %s coin(s) (cg_id=%s)",
                len(group),
                gid_key,
            )
            no_ticker_count += len(group)

    return no_ticker_count
