"""Tests for CoinGecko ticker volume parsing."""

from api.coingecko import coingecko_ticker_exchange_ids_csv
from scanner.market_processing import process_tickers


def test_coingecko_csv_maps_coinbase_to_gdax_and_coinbase_ids():
    csv = coingecko_ticker_exchange_ids_csv(["coinbase", "kraken", "mexc"])
    assert csv == "gdax,coinbase,kraken,mxc"


def test_process_tickers_matches_gdax_identifier_for_coinbase():
    tickers_data = {
        "tickers": [
            {
                "market": {
                    "identifier": "gdax",
                    "name": "Coinbase Exchange",
                },
                "converted_volume": {"usd": 1_500_000.0},
            }
        ]
    }
    vols = process_tickers(tickers_data, ("coinbase", "kraken", "mexc"))
    assert vols["coinbase"] == 1_500_000.0
    assert vols["kraken"] == "N/A"
    assert vols["mexc"] == "N/A"


def test_process_tickers_coinbase_after_many_kraken_pairs_like_pagination_merge():
    """CG returns max 100 tickers per page; Coinbase rows can land on page 2+ when merged."""
    kr = [
        {
            "market": {"identifier": "kraken", "name": "Kraken"},
            "converted_volume": {"usd": 900.0},
        }
    ] * 100
    gd = [
        {
            "market": {"identifier": "gdax", "name": "Coinbase Exchange"},
            "converted_volume": {"usd": 2_000_000.0},
        }
    ]
    vols = process_tickers({"tickers": kr + gd}, ("coinbase", "kraken", "mexc"))
    assert vols["coinbase"] == 2_000_000.0
    assert vols["kraken"] == 900.0


def test_process_tickers_identifier_coinbase_string():
    tickers_data = {
        "tickers": [
            {
                "market": {"identifier": "coinbase", "name": "Coinbase Exchange"},
                "converted_volume": {"usd": 88_000.0},
            }
        ]
    }
    vols = process_tickers(tickers_data, ("coinbase", "kraken", "mexc"))
    assert vols["coinbase"] == 88_000.0


def test_process_tickers_fallback_last_times_volume_when_no_converted_volume():
    tickers_data = {
        "tickers": [
            {
                "market": {"identifier": "gdax", "name": "Coinbase Exchange"},
                "converted_volume": None,
                "last": "2.0",
                "volume": 50_000.0,
            }
        ]
    }
    vols = process_tickers(tickers_data, ("coinbase", "kraken", "mexc"))
    assert vols["coinbase"] == 100_000.0
