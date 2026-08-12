"""Tradeable-only exchange listing parse (skip delisted / cancel_only pairs)."""

from __future__ import annotations

from unittest.mock import MagicMock

from exchange_data.exchange_fetcher import (
    ExchangeFetcher,
    coinbase_product_is_tradeable,
    kraken_pair_is_tradeable,
)


def test_coinbase_product_skips_delisted_and_trading_disabled():
    assert coinbase_product_is_tradeable(
        {"base_currency": "BTC", "status": "online", "trading_disabled": False}
    )
    assert not coinbase_product_is_tradeable(
        {"base_currency": "MATIC", "status": "delisted", "trading_disabled": True}
    )
    assert not coinbase_product_is_tradeable(
        {"base_currency": "X", "status": "online", "trading_disabled": True}
    )
    assert not coinbase_product_is_tradeable({"base_currency": "Y", "status": "offline"})


def test_kraken_pair_skips_cancel_only_keeps_post_only():
    assert kraken_pair_is_tradeable({"base": "XXBT", "status": "online"})
    assert kraken_pair_is_tradeable({"base": "AIO", "status": "post_only"})
    assert not kraken_pair_is_tradeable({"base": "ACX", "status": "cancel_only"})
    assert kraken_pair_is_tradeable({"base": "ETH"})  # missing status → treat as online


def test_fetch_coinbase_listings_omits_delisted_bases():
    fetcher = ExchangeFetcher(MagicMock())
    fetcher.session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = [
        {"base_currency": "BTC", "status": "online", "trading_disabled": False},
        {"base_currency": "MATIC", "status": "delisted", "trading_disabled": True},
        {"base_currency": "ETH", "status": "online", "trading_disabled": False},
        {"base_currency": "ETH", "status": "delisted", "trading_disabled": True},
    ]
    fetcher.session.get.return_value = response

    listings = fetcher.fetch_coinbase_listings()
    symbols = sorted({row["symbol"] for row in listings})
    assert symbols == ["BTC", "ETH"]


def test_fetch_kraken_listings_omits_cancel_only_only_bases():
    fetcher = ExchangeFetcher(MagicMock())
    fetcher.session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "error": [],
        "result": {
            # cancel_only first — must not permanently occupy the base in `seen`
            "ACXUSD": {"base": "ACX", "status": "cancel_only"},
            "ACXEUR": {"base": "ACX", "status": "online"},
            "BADUSD": {"base": "BAD", "status": "cancel_only"},
            "XBTUSD": {"base": "XXBT", "status": "online"},
            "AIOUSD": {"base": "AIO", "status": "post_only"},
        },
    }
    fetcher.session.get.return_value = response

    listings = fetcher.fetch_kraken_listings()
    symbols = sorted({row["symbol"] for row in listings})
    assert symbols == ["ACX", "AIO", "XXBT"]
    assert "BAD" not in symbols
