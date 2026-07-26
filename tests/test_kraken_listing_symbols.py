"""Kraken AssetPairs must store market symbols (BTC), not internal codes (XXBT)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from exchange_data.exchange_fetcher import ExchangeFetcher, normalize_kraken_base_symbol


def test_normalize_kraken_base_prefers_wsname_and_aliases() -> None:
    assert normalize_kraken_base_symbol({"base": "XXBT", "wsname": "XBT/USD"}) == "BTC"
    assert normalize_kraken_base_symbol({"base": "XETH", "wsname": "ETH/USD"}) == "ETH"
    assert normalize_kraken_base_symbol({"base": "XXDG", "wsname": "XDG/USD"}) == "DOGE"
    assert normalize_kraken_base_symbol({"base": "SOL", "wsname": "SOL/USD"}) == "SOL"
    assert normalize_kraken_base_symbol({"base": "ZUSD", "wsname": "USD/EUR"}) is None


def test_fetch_kraken_listings_stores_market_symbols_not_internal_codes() -> None:
    fetcher = ExchangeFetcher(exchange_db=MagicMock())
    payload: dict[str, Any] = {
        "error": [],
        "result": {
            "XXBTZUSD": {"base": "XXBT", "quote": "ZUSD", "wsname": "XBT/USD"},
            "XETHZUSD": {"base": "XETH", "quote": "ZUSD", "wsname": "ETH/USD"},
            "XXRPZUSD": {"base": "XXRP", "quote": "ZUSD", "wsname": "XRP/USD"},
            "XXDGZUSD": {"base": "XXDG", "quote": "ZUSD", "wsname": "XDG/USD"},
            "SOLUSD": {"base": "SOL", "quote": "ZUSD", "wsname": "SOL/USD"},
            "SOLXBT": {"base": "SOL", "quote": "XXBT", "wsname": "SOL/XBT"},
        },
    }
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    fetcher.session.get = MagicMock(return_value=response)

    listings = fetcher.fetch_kraken_listings()
    symbols = {row["symbol"] for row in listings}

    assert "BTC" in symbols
    assert "ETH" in symbols
    assert "XRP" in symbols
    assert "DOGE" in symbols
    assert "SOL" in symbols
    assert "XXBT" not in symbols
    assert "XETH" not in symbols
    assert "XBT" not in symbols
    assert "XDG" not in symbols
