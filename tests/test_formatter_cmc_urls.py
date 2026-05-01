"""Golden-style checks for CMC vs CoinGecko URL selection (no CMC /search/ fallbacks)."""

from __future__ import annotations

from notifications.formatter import MessageFormatter


def test_build_cmc_url_from_slug() -> None:
    url = MessageFormatter._build_cmc_url({"cmc_slug": "bitcoin"})
    assert "/currencies/bitcoin/" in url
    assert "search" not in url.lower()


def test_build_cmc_url_rejects_symbol_only_search() -> None:
    """Legacy behavior used CMC search; we return empty so primary_market_url can use CoinGecko."""
    url = MessageFormatter._build_cmc_url({"symbol": "BTC", "slug": "bitcoin", "gecko_id": "bitcoin"})
    assert url == ""


def test_build_cmc_url_skips_explicit_search_url() -> None:
    url = MessageFormatter._build_cmc_url(
        {
            "cmc_url": "https://coinmarketcap.com/search/?q=BTC",
            "cmc_slug": "bitcoin",
        }
    )
    assert "/currencies/bitcoin/" in url
    assert "search" not in url.lower()


def test_primary_market_url_falls_back_to_coingecko() -> None:
    url = MessageFormatter.primary_market_url(
        {"symbol": "BTC", "slug": "bitcoin", "gecko_id": "bitcoin"},
    )
    assert "coingecko.com" in url.lower()
    assert "search" not in url.lower()


def test_primary_market_url_skips_source_search() -> None:
    url = MessageFormatter.primary_market_url(
        {
            "symbol": "BTC",
            "slug": "bitcoin",
            "gecko_id": "bitcoin",
            "source_url": "https://coinmarketcap.com/search/?q=BTC",
        },
    )
    assert "coingecko.com" in url.lower()


def test_format_entry_header_uses_cmc_currency_path() -> None:
    coin = {
        "symbol": "BTC",
        "name": "Bitcoin",
        "gains": {"7d": 1.0, "30d": 2.0},
        "uniformity_score": 80,
        "cmc_slug": "bitcoin",
        "exchange_volumes": {},
        "listed_on": [],
    }
    caption = MessageFormatter.format_entry(coin)
    assert "coinmarketcap.com/currencies/bitcoin" in caption
    assert "coinmarketcap.com/search" not in caption.lower()
