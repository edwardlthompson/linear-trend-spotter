"""Per-subscriber filtering for qualified-list Web Push (exchange preferences)."""

from __future__ import annotations

from typing import Any


def normalize_notify_exchange_ids(raw: Any) -> list[str]:
    """Lowercase exchange ids from subscribe body; empty = notify for all listings."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x or "").strip().lower()
        if s:
            out.append(s)
    return sorted(set(out))[:24]


def coin_matches_notify_exchanges(coin: dict[str, Any], notify_ids: list[str]) -> bool:
    """True if subscriber wants this coin (same rule as dashboard: any selected exchange in listed_on)."""
    if not notify_ids:
        return True
    lo = coin.get("listed_on")
    if isinstance(lo, str) and lo.strip():
        lo = [lo]
    if not isinstance(lo, list) or not lo:
        return False
    lo_set = {str(x).strip().lower() for x in lo if str(x).strip()}
    want = set(notify_ids)
    return bool(lo_set & want)


def filter_events_for_subscriber(
    notify_ids: list[str],
    entered_coins: list[dict[str, Any]],
    exited_coins: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ent = [c for c in entered_coins if isinstance(c, dict) and coin_matches_notify_exchanges(c, notify_ids)]
    ext = [c for c in exited_coins if isinstance(c, dict) and coin_matches_notify_exchanges(c, notify_ids)]
    return ent, ext


def format_change_body(entered: list[dict[str, Any]], exited: list[dict[str, Any]], *, max_symbols: int = 10) -> str:
    """Build compact body text (<=240 chars) from filtered coin dicts."""
    parts: list[str] = []

    def _syms(rows: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for row in rows:
            sym = str(row.get("symbol", "")).upper().strip()
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
        out.sort()
        return out

    ent_syms = _syms(entered)
    ext_syms = _syms(exited)
    if ent_syms:
        shown = ent_syms[:max_symbols]
        suffix = f" (+{len(ent_syms) - len(shown)} more)" if len(ent_syms) > len(shown) else ""
        parts.append("In: " + ", ".join(shown) + suffix)
    elif entered:
        parts.append(f"In: {len(entered)} symbol(s)")
    if ext_syms:
        shown = ext_syms[:max_symbols]
        suffix = f" (+{len(ext_syms) - len(shown)} more)" if len(ext_syms) > len(shown) else ""
        parts.append("Out: " + ", ".join(shown) + suffix)
    elif exited:
        parts.append(f"Out: {len(exited)} symbol(s)")
    body = " · ".join(parts) if parts else "Open the qualified dashboard."
    if len(body) > 240:
        body = body[:237] + "…"
    return body
