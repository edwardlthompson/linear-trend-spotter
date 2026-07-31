"""Regression: dashboard volume→listing fallback must ignore N/A stubs.

Mirrors ``explodeCoinRowsForTable`` in ``docs/dashboard/app.js`` (keep in sync).
Scanner ``process_tickers`` always emits every target exchange key, often as
``\"N/A\"``. Using ``Object.keys(exchange_volumes)`` as a listing fallback then
falsely attributes coins to every venue when ``listed_on`` is empty.
"""

from __future__ import annotations

from typing import Any


def _parse_vol_usd(raw: Any) -> float | None:
    if raw is None or raw == "" or str(raw).upper() == "N/A":
        return None
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    return n if n == n else None  # NaN check


def explode_exchange_ids(
    coin: dict[str, Any],
    *,
    target_ids: set[str] | None = None,
) -> list[str | None]:
    """Return exchange ids for table/alert rows (None = unscoped single row)."""
    targets = target_ids or {"coinbase", "kraken", "mexc"}
    if coin.get("_watchlist_only"):
        return [None]
    ev = coin.get("exchange_volumes") if isinstance(coin.get("exchange_volumes"), dict) else {}
    listed_raw = coin.get("listed_on") if isinstance(coin.get("listed_on"), list) else []
    listed = [str(x or "").strip().lower() for x in listed_raw if str(x or "").strip()]
    from_vol = [
        str(k or "").strip().lower()
        for k in ev
        if str(k or "").strip() and _parse_vol_usd(ev[k]) is not None
    ]
    keys_source = listed if listed else from_vol
    uniq = sorted({k for k in keys_source if k in targets})
    return uniq if uniq else [None]


def test_na_volume_keys_are_not_treated_as_listings() -> None:
    coin = {
        "symbol": "ZZZ",
        "listed_on": [],
        "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "N/A"},
    }
    assert explode_exchange_ids(coin) == [None]


def test_numeric_volume_fallback_when_listed_on_empty() -> None:
    coin = {
        "symbol": "ABC",
        "listed_on": [],
        "exchange_volumes": {"coinbase": "N/A", "kraken": 1200.5, "mexc": "N/A"},
    }
    assert explode_exchange_ids(coin) == ["kraken"]


def test_listed_on_wins_over_volume_keys() -> None:
    coin = {
        "symbol": "ADA",
        "listed_on": ["kraken"],
        "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": 99},
    }
    assert explode_exchange_ids(coin) == ["kraken"]


def test_empty_listed_on_with_mixed_volumes_does_not_invent_coinbase() -> None:
    """Concrete Tier-A false-positive trigger before the fix."""
    coin = {
        "symbol": "GHOST",
        "listed_on": [],
        "exchange_volumes": {"coinbase": "N/A", "kraken": "N/A", "mexc": "N/A"},
    }
    ids = explode_exchange_ids(coin)
    assert "coinbase" not in ids
    assert "kraken" not in ids
    assert "mexc" not in ids
