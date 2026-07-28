"""Top-coin provider snapshot (STEP 1) — Milestone I2 pipeline extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scanner.cmc_resolve import build_cmc_normalized_lookup


def _provider_rank(info: dict[str, Any]) -> int:
    """Lower market-cap rank wins; missing/invalid ranks sort last."""
    try:
        rank = int(info.get("rank") or 0)
    except (TypeError, ValueError):
        return 10**9
    return rank if rank > 0 else 10**9


@dataclass(frozen=True, slots=True)
class TopCoinsDataset:
    all_cmc_coins: list[dict[str, Any]]
    cmc_by_symbol: dict[str, dict[str, Any]]
    cmc_by_normalized_symbol: dict[str, list[tuple[str, dict[str, Any]]]]
    cmc_symbol_aliases: dict[str, str]
    coingecko_id_aliases: dict[str, str]


def fetch_top_coins_dataset(
    *,
    top_coins_provider: str,
    top_coins_limit: int,
    cmc_symbol_aliases: dict[str, str],
    coingecko_id_aliases: dict[str, str],
    gecko: Any,
    cmc: Any,
    app_logger: Any,
    metrics: Any,
) -> TopCoinsDataset | None:
    """Load ranked coins with gains from CoinGecko or CMC. Returns None if the provider call fails."""
    all_cmc_coins: list[dict[str, Any]] = []
    if top_coins_provider == "coingecko":
        gecko_rows = gecko.get_top_coins_with_gains(limit=top_coins_limit)
        if not gecko_rows:
            app_logger.error("❌ Failed to fetch coins from CoinGecko")
            return None

        for index, row in enumerate(gecko_rows, start=1):
            symbol = str(row.get("symbol", "")).upper()
            if not symbol:
                continue
            gecko_id = str(row.get("id", "")).strip()
            gains = {
                "7d": float(row.get("price_change_percentage_7d_in_currency", 0) or 0),
                "30d": float(row.get("price_change_percentage_30d_in_currency", 0) or 0),
                "60d": 0.0,
                "90d": 0.0,
            }
            info = {
                "symbol": symbol,
                "name": str(row.get("name", "")).strip(),
                "slug": gecko_id,
                "gecko_id": gecko_id,
                "rank": int(row.get("market_cap_rank") or index),
                "price": float(row.get("current_price", 0) or 0),
                "volume_24h": float(row.get("total_volume", 0) or 0),
                "source_url": f"https://www.coingecko.com/en/coins/{gecko_id}" if gecko_id else None,
            }
            all_cmc_coins.append(
                {
                    "data": row,
                    "gains": gains,
                    "info": info,
                }
            )
    else:
        cmc_rows = cmc.get_all_coins_with_gains(limit=top_coins_limit)
        if not cmc_rows:
            app_logger.error("❌ Failed to fetch coins from CMC")
            return None

        for row in cmc_rows:
            symbol = str(row.get("symbol", "")).upper()
            if not symbol:
                continue
            all_cmc_coins.append(
                {
                    "data": row,
                    "gains": cmc.extract_gains(row),
                    "info": cmc.extract_coin_data(row),
                }
            )

    app_logger.info(f"✅ Got {len(all_cmc_coins)} coins with gain data")
    metrics.increment("coins_retrieved", len(all_cmc_coins))

    # Providers return market-cap order but reuse tickers (RAIN, FUN, …). Last-wins
    # would bind exchange symbols to the lowest-ranked clone and corrupt gains/volume.
    cmc_by_symbol: dict[str, dict[str, Any]] = {}
    for coin in all_cmc_coins:
        info = coin.get("info") or {}
        symbol = str(info.get("symbol", "")).upper()
        if not symbol:
            continue
        payload = {
            "data": coin.get("data", {}),
            "gains": coin.get("gains", {}),
            "info": info,
        }
        existing = cmc_by_symbol.get(symbol)
        if existing is None or _provider_rank(info) < _provider_rank(existing.get("info") or {}):
            cmc_by_symbol[symbol] = payload

    cmc_by_normalized_symbol = build_cmc_normalized_lookup(cmc_by_symbol)

    return TopCoinsDataset(
        all_cmc_coins=all_cmc_coins,
        cmc_by_symbol=cmc_by_symbol,
        cmc_by_normalized_symbol=cmc_by_normalized_symbol,
        cmc_symbol_aliases=cmc_symbol_aliases,
        coingecko_id_aliases=coingecko_id_aliases,
    )
