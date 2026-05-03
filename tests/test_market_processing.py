"""Tests for CoinGecko ticker volume parsing."""

from api.coingecko import coingecko_ticker_exchange_ids_csv
from scanner.market_processing import process_tickers


def test_coingecko_csv_maps_coinbase_to_gdax():
    csv = coingecko_ticker_exchange_ids_csv(["coinbase", "kraken", "mexc"])
    assert csv == "gdax,kraken,mxc"


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
