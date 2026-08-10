"""Gain and 24h volume filter (STEP 3) — Milestone I2 pipeline extraction."""

from __future__ import annotations

from urllib.parse import quote
from typing import Any

from config.constants import STABLECOINS
from scanner.top_coin_resolution import resolve_top_coin_data


def apply_gain_volume_filter(
    all_symbols: list[str],
    *,
    top_coins_provider: str,
    min_volume: float,
    gain_filter_min_7d_percent: float,
    gain_filter_min_30d_percent: float,
    cmc_by_symbol: dict[str, dict],
    cmc_by_normalized_symbol: dict[str, list[tuple[str, dict]]],
    cmc_symbol_aliases: dict[str, str],
    coingecko_id_aliases: dict[str, str],
    gecko: Any,
    alias_markets_by_id: dict[str, dict],
    cmc_slug_resolver: Any,
    app_logger: Any,
    metrics: Any,
) -> list[dict[str, Any]]:
    """
    Keep exchange-listed symbols that match provider gains/volume thresholds.
    Detailed per-symbol logs are capped for performance.
    """
    app_logger.info(
        f"\n💰 FILTER 1: Applying volume and gain filters ({top_coins_provider.upper()}) "
        f"(7d≥{gain_filter_min_7d_percent:g}%, 30d>{gain_filter_min_30d_percent:g}%, 30d>7d)..."
    )

    max_detailed_filter_logs = 180
    detailed_filter_logs_emitted = 0
    suppressed_filter_logs = 0
    filter_failure_counts: dict[str, int] = {
        "stablecoin": 0,
        "missing_provider": 0,
        "volume_low": 0,
        "gains_low": 0,
    }

    def _log_filter_line(message: str) -> None:
        nonlocal detailed_filter_logs_emitted, suppressed_filter_logs
        if detailed_filter_logs_emitted < max_detailed_filter_logs:
            app_logger.info(message)
            detailed_filter_logs_emitted += 1
        else:
            suppressed_filter_logs += 1

    gain_qualified: list[dict[str, Any]] = []

    for symbol in all_symbols:
        if symbol in STABLECOINS:
            filter_failure_counts["stablecoin"] += 1
            _log_filter_line(f"   ⏭️ {symbol}: Skipped (stablecoin)")
            continue

        cmc_data, resolved_cmc_symbol, resolution_type = resolve_top_coin_data(
            symbol,
            top_coins_provider=top_coins_provider,
            cmc_by_symbol=cmc_by_symbol,
            cmc_by_normalized_symbol=cmc_by_normalized_symbol,
            cmc_symbol_aliases=cmc_symbol_aliases,
            coingecko_id_aliases=coingecko_id_aliases,
            gecko=gecko,
            alias_markets_by_id=alias_markets_by_id,
        )

        if cmc_data:
            if resolution_type != "direct":
                if top_coins_provider == "coingecko" and resolution_type == "coingecko_id_alias":
                    _log_filter_line(
                        f"   ↪️ {symbol}: Matched CoinGecko id {resolved_cmc_symbol} via {resolution_type}"
                    )
                else:
                    _log_filter_line(
                        f"   ↪️ {symbol}: Matched CMC symbol {resolved_cmc_symbol} via {resolution_type}"
                    )
            gains = cmc_data["gains"]
            info = cmc_data["info"]

            vol_24h = float(info.get("volume_24h") or 0)
            g7 = float(gains.get("7d") or 0)
            g30 = float(gains.get("30d") or 0)
            if vol_24h >= min_volume:
                min7 = float(gain_filter_min_7d_percent)
                min30 = float(gain_filter_min_30d_percent)
                if g7 >= min7 and g30 > min30 and g30 > g7:
                    coin_info: dict[str, Any] = {
                        "symbol": symbol,
                        "cmc_symbol": resolved_cmc_symbol,
                        "name": info["name"],
                        "slug": info["slug"],
                        "source_url": info.get("source_url"),
                        "cmc_url": info.get("cmc_url"),
                        "gains": {"7d": g7, "30d": g30, "60d": float(gains.get("60d") or 0), "90d": float(gains.get("90d") or 0)},
                        "volume_24h": vol_24h,
                        "current_price": float(info.get("price", 0) or 0),
                        "provider_symbol_resolution": resolution_type,
                    }
                    raw_cmc_id = info.get("cmc_id")
                    if raw_cmc_id is not None:
                        try:
                            coin_info["cmc_id"] = int(raw_cmc_id)
                        except (TypeError, ValueError):
                            pass
                    gecko_for_link = str(info.get("gecko_id") or "").strip().lower()
                    if top_coins_provider == "coingecko":
                        coin_info["gecko_id"] = gecko_for_link
                        if cmc_slug_resolver and gecko_for_link:
                            resolved_slug, resolved_cid, slug_tag = cmc_slug_resolver.resolve_identity(
                                symbol=symbol,
                                name=str(info.get("name") or ""),
                                gecko_id=gecko_for_link,
                            )
                            if resolved_slug:
                                cu = f"https://coinmarketcap.com/currencies/{quote(resolved_slug, safe='')}/"
                                coin_info["cmc_slug"] = resolved_slug
                                coin_info["cmc_url"] = cu
                                coin_info["source_url"] = cu
                                coin_info["cmc_slug_resolution"] = slug_tag
                                if resolved_cid is not None and coin_info.get("cmc_id") is None:
                                    coin_info["cmc_id"] = int(resolved_cid)
                    elif top_coins_provider == "cmc":
                        cmc_slug_key = str(info.get("slug") or "").strip().lower()
                        if cmc_slug_key:
                            coin_info["cmc_slug"] = cmc_slug_key
                        coin_info["cmc_slug_resolution"] = "cmc_listings"
                    gain_qualified.append(coin_info)
                    _log_filter_line(
                        f"   ✓ {symbol}: 7d:{g7:.1f}% 30d:{g30:.1f}% "
                        f"Vol:${vol_24h:,.0f}"
                    )
                else:
                    filter_failure_counts["gains_low"] += 1
                    if g7 < min7:
                        why = f"7d below min ({g7:.1f}% < {min7:g}%)"
                    elif g30 <= min30:
                        why = f"30d not above min ({g30:.1f}% ≤ {min30:g}%)"
                    else:
                        why = f"30d not above 7d ({g30:.1f}% ≤ {g7:.1f}%)"
                    _log_filter_line(f"   ❌ {symbol}: Gains filter — {why}")
            else:
                filter_failure_counts["volume_low"] += 1
                _log_filter_line(f"   ❌ {symbol}: Volume too low (${vol_24h:,.0f})")
        else:
            filter_failure_counts["missing_provider"] += 1
            _log_filter_line(f"   ❌ {symbol}: Not found in {top_coins_provider.upper()} data")

    app_logger.info(f"\n   ✅ PASSED gain filter: {len(gain_qualified)} coins")
    if suppressed_filter_logs > 0:
        app_logger.info(
            "   ℹ️ Filter detail logs suppressed for speed: "
            f"{suppressed_filter_logs} lines omitted after first {max_detailed_filter_logs}"
        )
    app_logger.info(
        "   📉 Filter failure summary: "
        f"stablecoin={filter_failure_counts['stablecoin']}, "
        f"missing_provider={filter_failure_counts['missing_provider']}, "
        f"volume_low={filter_failure_counts['volume_low']}, "
        f"gains_low={filter_failure_counts['gains_low']}"
    )
    metrics.increment("gain_filter_passed", len(gain_qualified))
    return gain_qualified
