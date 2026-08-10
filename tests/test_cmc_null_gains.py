"""CMC listings use JSON null for inapplicable percent/volume fields — must not crash scans."""

from __future__ import annotations

from api.coinmarketcap import CoinMarketCapClient
from scanner.gain_volume_filter import apply_gain_volume_filter


class _Log:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None


class _Metrics:
    def increment(self, *args, **kwargs) -> None:
        return None


def test_extract_gains_coerces_null_percent_changes() -> None:
    client = CoinMarketCapClient("unused")
    gains = client.extract_gains(
        {
            "quote": {
                "USD": {
                    "percent_change_7d": None,
                    "percent_change_30d": None,
                    "percent_change_60d": None,
                    "percent_change_90d": None,
                }
            }
        }
    )
    assert gains == {"7d": 0.0, "30d": 0.0, "60d": 0.0, "90d": 0.0}


def test_extract_coin_data_coerces_null_price_and_volume() -> None:
    client = CoinMarketCapClient("unused")
    info = client.extract_coin_data(
        {
            "symbol": "NEW",
            "name": "New Coin",
            "slug": "new-coin",
            "cmc_rank": 9001,
            "quote": {"USD": {"price": None, "volume_24h": None}},
        }
    )
    assert info["price"] == 0.0
    assert info["volume_24h"] == 0.0


def test_gain_volume_filter_survives_null_cmc_fields() -> None:
    """Default TOP_COINS_PROVIDER=cmc: one null-gain listing must not abort FILTER 1."""
    cmc_by_symbol = {
        "NEWCOIN": {
            "data": {},
            "gains": {"7d": None, "30d": None, "60d": None, "90d": None},
            "info": {
                "symbol": "NEWCOIN",
                "name": "New Coin",
                "slug": "new-coin",
                "volume_24h": None,
                "price": None,
            },
        },
        "BTC": {
            "data": {},
            "gains": {"7d": 5.0, "30d": 12.0, "60d": 0.0, "90d": 0.0},
            "info": {
                "symbol": "BTC",
                "name": "Bitcoin",
                "slug": "bitcoin",
                "volume_24h": 1_000_000_000.0,
                "price": 100_000.0,
            },
        },
    }
    qualified = apply_gain_volume_filter(
        ["BTC", "NEWCOIN"],
        top_coins_provider="cmc",
        min_volume=0.0,
        gain_filter_min_7d_percent=0.0,
        gain_filter_min_30d_percent=0.0,
        cmc_by_symbol=cmc_by_symbol,
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gecko=None,
        alias_markets_by_id={},
        cmc_slug_resolver=None,
        app_logger=_Log(),
        metrics=_Metrics(),
    )
    symbols = {c["symbol"] for c in qualified}
    assert "BTC" in symbols
    assert "NEWCOIN" not in symbols
