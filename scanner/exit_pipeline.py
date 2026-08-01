"""Per-exit reason strings and active DB registration — Milestone I2."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config.constants import STABLECOINS
from scanner.top_coin_resolution import resolve_top_coin_data


def exclude_cooldown_blocked_coins(
    coins: list[dict[str, Any]],
    blocked_by_cooldown: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Omit cooldown-blocked symbols from the public qualified/snapshot set.

    Active-DB skips re-entry while cooling down; keeping those symbols in
    ``final_results`` published ghosts (Tier-A appear/disappear without B/C).
    """
    if not coins or not blocked_by_cooldown:
        return coins
    blocked = {
        str(row.get("symbol") or "").strip().upper()
        for row in blocked_by_cooldown
        if row.get("symbol")
    }
    if not blocked:
        return coins
    return [
        c for c in coins if str(c.get("symbol") or "").strip().upper() not in blocked
    ]


def attach_exit_reasons_and_register(
    exited: list[dict[str, Any]],
    *,
    active_db: Any,
    settings: Any,
    all_symbols_set: set[str],
    top_coins_provider: str,
    cmc_by_symbol: dict[str, Any],
    cmc_by_normalized_symbol: Any,
    cmc_symbol_aliases: dict[str, str],
    coingecko_id_aliases: dict[str, str],
    gecko: Any,
    alias_markets_by_id: dict[str, dict],
    gain_qualified_symbols: set[str],
    coins_with_cg_ids_symbols: set[str],
    all_processed_map: dict[str, dict[str, Any]],
    uniformity_passed_symbols: set[str],
) -> None:
    for coin in exited:
        symbol = coin["symbol"]
        coin["exited_at"] = datetime.now(timezone.utc).isoformat()
        coin["cooldown_until"] = (
            datetime.now(timezone.utc) + timedelta(hours=settings.alert_cooldown_hours)
        ).isoformat()

        if symbol in STABLECOINS:
            coin["exit_reason"] = "Filtered as stablecoin"
            continue

        if symbol not in all_symbols_set:
            coin["exit_reason"] = "No longer listed on target exchanges"
            continue

        cmc_data, _, _ = resolve_top_coin_data(
            symbol,
            top_coins_provider=top_coins_provider,
            cmc_by_symbol=cmc_by_symbol,
            cmc_by_normalized_symbol=cmc_by_normalized_symbol,
            cmc_symbol_aliases=cmc_symbol_aliases,
            coingecko_id_aliases=coingecko_id_aliases,
            gecko=gecko,
            alias_markets_by_id=alias_markets_by_id,
        )
        if not cmc_data:
            if top_coins_provider == "coingecko":
                coin["exit_reason"] = "Missing from current CoinGecko top-coin provider snapshot"
            else:
                coin["exit_reason"] = "Missing from current CoinMarketCap snapshot"
            continue

        gains = cmc_data["gains"]
        info = cmc_data["info"]
        coin["gain_7d"] = float(gains.get("7d", 0) or 0)
        coin["gain_30d"] = float(gains.get("30d", 0) or 0)
        coin["volume_24h"] = float(info.get("volume_24h", 0) or 0)

        if info["volume_24h"] < settings.min_volume:
            coin["exit_reason"] = (
                f"24h volume below threshold (${info['volume_24h']:,.0f} < ${settings.min_volume:,.0f})"
            )
            continue

        gain_7d = float(gains.get("7d", 0) or 0)
        gain_30d = float(gains.get("30d", 0) or 0)
        min7 = float(settings.gain_filter_min_7d_percent)
        min30 = float(settings.gain_filter_min_30d_percent)
        if gain_7d < min7:
            coin["exit_reason"] = f"7d gain below threshold ({gain_7d:.1f}% < {min7:g}%)"
            continue
        if gain_30d <= min30:
            coin["exit_reason"] = f"30d gain below threshold ({gain_30d:.1f}% ≤ {min30:g}%)"
            continue
        if gain_30d <= gain_7d:
            coin["exit_reason"] = f"30d gain not higher than 7d ({gain_30d:.1f}% ≤ {gain_7d:.1f}%)"
            continue

        if symbol not in gain_qualified_symbols:
            coin["exit_reason"] = "Failed gain/volume filter"
            continue

        if symbol not in coins_with_cg_ids_symbols:
            coin["exit_reason"] = "No CoinGecko ID mapping"
            continue

        if symbol not in all_processed_map:
            coin["exit_reason"] = "Insufficient or missing 30d price history"
            continue

        processed_coin = all_processed_map[symbol]
        coin["uniformity_score"] = float(processed_coin.get("uniformity_score", 0) or 0)
        coin["health_score"] = processed_coin.get("health_score")
        if processed_coin.get("uniformity_score", 0) < settings.uniformity_min_score:
            coin["exit_reason"] = (
                f"Uniformity score below threshold ({processed_coin.get('uniformity_score', 0):.1f} "
                f"< {settings.uniformity_min_score})"
            )
            continue

        if processed_coin.get("total_gain", 0) <= 0:
            coin["exit_reason"] = f"30d return non-positive ({processed_coin.get('total_gain', 0):.1f}%)"
            continue

        if symbol not in uniformity_passed_symbols:
            coin["exit_reason"] = "Failed final uniformity qualification"
            continue

        coin["exit_reason"] = "No longer met qualification criteria"

    for coin in exited:
        active_db.register_exit(
            coin["symbol"],
            reason=str(coin.get("exit_reason", "No longer qualified")),
            cooldown_hours=settings.alert_cooldown_hours,
        )
