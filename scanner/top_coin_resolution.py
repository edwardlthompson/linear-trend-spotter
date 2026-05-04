"""Top-coin resolution and notify-link normalization (Milestone I2 extraction)."""

from __future__ import annotations

from urllib.parse import quote
from typing import Any

from scanner.cmc_resolve import resolve_cmc_data


def ensure_cmc_notify_urls(coin: dict, cmc_slug_resolver) -> None:
    """Prefer `/currencies/{slug}/` links and avoid CMC search URLs in notifications."""
    for key in ("cmc_url", "source_url"):
        raw = str(coin.get(key) or "").strip()
        if "coinmarketcap.com/search" in raw.lower():
            coin[key] = ""
    if str(coin.get("cmc_slug") or "").strip() and coin.get("cmc_id") is not None:
        return
    if not cmc_slug_resolver:
        return
    gid = str(coin.get("gecko_id") or coin.get("cg_id") or "").strip().lower()
    if not gid:
        return
    slug, cmc_id, tag = cmc_slug_resolver.resolve_identity(
        symbol=str(coin.get("symbol") or ""),
        name=str(coin.get("name") or ""),
        gecko_id=gid,
    )
    if not slug:
        return
    cu = f"https://coinmarketcap.com/currencies/{quote(str(slug).strip().lower(), safe='')}/"
    coin["cmc_slug"] = str(slug).strip().lower()
    if cmc_id is not None and coin.get("cmc_id") is None:
        coin["cmc_id"] = int(cmc_id)
    if not coin.get("cmc_slug_resolution"):
        coin["cmc_slug_resolution"] = tag
    coin["cmc_url"] = cu
    if not str(coin.get("source_url") or "").strip():
        coin["source_url"] = cu


def resolve_top_coin_data(
    symbol: str,
    *,
    top_coins_provider: str,
    cmc_by_symbol: dict[str, dict],
    cmc_by_normalized_symbol: dict[str, list[tuple[str, dict]]],
    cmc_symbol_aliases: dict[str, str],
    coingecko_id_aliases: dict[str, str],
    gecko: Any,
    alias_markets_by_id: dict[str, dict] | None = None,
) -> tuple[dict | None, str | None, str]:
    resolved_data, resolved_symbol, resolution_type = resolve_cmc_data(
        symbol,
        cmc_by_symbol,
        cmc_by_normalized_symbol,
        cmc_symbol_aliases,
    )
    if resolved_data or top_coins_provider != "coingecko":
        return resolved_data, resolved_symbol, resolution_type

    symbol_upper = str(symbol or "").upper()
    alias_gecko_id = coingecko_id_aliases.get(symbol_upper)
    if not alias_gecko_id:
        return None, None, "missing"

    alias_key = str(alias_gecko_id).strip().lower()
    row = (alias_markets_by_id or {}).get(alias_key)
    if row:
        alias_snapshot = gecko.snapshot_from_markets_row(row, symbol_override=symbol_upper)
    else:
        # Prefer chunked /coins/markets (same credit model) before /coins/{id}
        chunk = gecko.get_markets_rows_for_ids([alias_key])
        row2 = chunk.get(alias_key) if chunk else None
        if row2:
            alias_snapshot = gecko.snapshot_from_markets_row(row2, symbol_override=symbol_upper)
            if alias_markets_by_id is not None:
                alias_markets_by_id[alias_key] = row2
        else:
            alias_snapshot = gecko.get_coin_market_snapshot(alias_gecko_id)
    if not alias_snapshot:
        return None, None, "missing"

    alias_info = dict(alias_snapshot.get("info") or {})
    alias_info["symbol"] = symbol_upper
    alias_info.setdefault("source_url", f"https://www.coingecko.com/en/coins/{alias_gecko_id}")
    resolved_data = {
        "data": alias_snapshot.get("data", {}),
        "gains": alias_snapshot.get("gains", {}),
        "info": alias_info,
    }
    cmc_by_symbol[symbol_upper] = resolved_data
    return resolved_data, alias_gecko_id, "coingecko_id_alias"
