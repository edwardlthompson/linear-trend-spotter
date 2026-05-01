"""CoinMarketCap symbol matching helpers (extracted from main.py, Milestone I2)."""


def normalize_symbol(raw_symbol: str) -> str:
    return "".join(ch for ch in str(raw_symbol or "").upper() if ch.isalnum())


def build_cmc_normalized_lookup(cmc_by_symbol: dict[str, dict]) -> dict[str, list[tuple[str, dict]]]:
    lookup: dict[str, list[tuple[str, dict]]] = {}
    for symbol, payload in cmc_by_symbol.items():
        normalized = normalize_symbol(symbol)
        if not normalized:
            continue
        lookup.setdefault(normalized, []).append((symbol, payload))
    return lookup


def resolve_cmc_data(
    symbol: str,
    cmc_by_symbol: dict[str, dict],
    cmc_by_normalized_symbol: dict[str, list[tuple[str, dict]]],
    symbol_aliases: dict[str, str],
) -> tuple[dict | None, str | None, str]:
    symbol_upper = str(symbol or "").upper()
    if not symbol_upper:
        return None, None, "missing"

    direct = cmc_by_symbol.get(symbol_upper)
    if direct:
        return direct, symbol_upper, "direct"

    alias_target = symbol_aliases.get(symbol_upper)
    if alias_target:
        alias_direct = cmc_by_symbol.get(alias_target)
        if alias_direct:
            return alias_direct, alias_target, "configured_alias"

        alias_normalized = normalize_symbol(alias_target)
        alias_candidates = cmc_by_normalized_symbol.get(alias_normalized, [])
        if len(alias_candidates) == 1:
            matched_symbol, matched_payload = alias_candidates[0]
            return matched_payload, matched_symbol, "configured_alias_normalized"

    normalized_symbol = normalize_symbol(symbol_upper)
    normalized_candidates = cmc_by_normalized_symbol.get(normalized_symbol, [])
    if len(normalized_candidates) == 1:
        matched_symbol, matched_payload = normalized_candidates[0]
        return matched_payload, matched_symbol, "normalized"

    return None, None, "missing"
