"""Normalize cross-vendor identifiers for qualified coins (CoinGecko / CMC / Polygon)."""

from __future__ import annotations

from typing import Any


def polygon_crypto_agg_ticker(symbol: str) -> str | None:
    """Polygon aggregate ticker used by ``PriceHistoryFallbackClient`` (``X:SYMUSD``)."""
    sym = str(symbol or "").strip().upper()
    if not sym or not sym.isalnum():
        return None
    return f"X:{sym}USD"


def build_identity_bundle(
    coin: dict[str, Any],
    *,
    top_coins_provider: str,
) -> dict[str, Any]:
    """JSON-safe identity block for snapshots and debugging (no secrets)."""
    sym = str(coin.get("symbol") or "").strip().upper()
    cg = str(coin.get("cg_id") or coin.get("gecko_id") or "").strip().lower() or None

    raw_cmc = coin.get("cmc_id")
    cmc_id: int | None = None
    if raw_cmc is not None:
        try:
            cmc_id = int(raw_cmc)
        except (TypeError, ValueError):
            cmc_id = None

    cmc_slug = str(coin.get("cmc_slug") or "").strip().lower() or None
    if not cmc_slug:
        raw_page = str(coin.get("slug") or "").strip().lower()
        if top_coins_provider == "cmc" and raw_page and raw_page != cg:
            cmc_slug = raw_page

    return {
        "cg_id": cg,
        "cmc_id": cmc_id,
        "cmc_slug": cmc_slug,
        "polygon_ticker": polygon_crypto_agg_ticker(sym),
        "top_coins_provider": str(top_coins_provider or "").strip().lower() or None,
        "provider_symbol_resolution": coin.get("provider_symbol_resolution"),
        "cmc_slug_resolution": coin.get("cmc_slug_resolution"),
        "ohlcv_source": coin.get("ohlcv_source"),
    }


def attach_identity_bundles(
    coins: list[dict[str, Any]],
    *,
    top_coins_provider: str,
) -> None:
    """Mutates each coin with ``coin['identity'] = build_identity_bundle(...)``."""
    top = str(top_coins_provider or "").strip().lower() or "coingecko"
    for row in coins:
        row["identity"] = build_identity_bundle(row, top_coins_provider=top)
