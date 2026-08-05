"""CMC OHLCV must not merge quotes from multiple assets that share a ticker."""

from __future__ import annotations

from api.price_history_fallback import PriceHistoryFallbackClient
from scanner.market_processing import aggregate_daily_bars_from_hourly


def _quote(ts: str, open_: float, high: float, low: float, close: float) -> dict:
    return {
        "time_open": ts,
        "quote": {
            "USD": {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1_000.0,
            }
        },
    }


def test_parse_cmc_hourly_refuses_ambiguous_symbol_list() -> None:
    payload = {
        "data": [
            {
                "id": 111,
                "name": "Rain Major",
                "symbol": "RAIN",
                "quotes": [
                    _quote("2024-01-01T00:00:00Z", 10.0, 11.0, 9.0, 10.5),
                    _quote("2024-01-01T01:00:00Z", 10.5, 12.0, 10.0, 11.0),
                ],
            },
            {
                "id": 999,
                "name": "Rain Clone",
                "symbol": "RAIN",
                "quotes": [
                    _quote("2024-01-01T00:00:00Z", 0.01, 0.02, 0.005, 0.015),
                    _quote("2024-01-01T01:00:00Z", 0.015, 0.03, 0.01, 0.02),
                ],
            },
        ]
    }
    rows = PriceHistoryFallbackClient._parse_cmc_hourly_quotes(payload)
    assert rows == []


def test_parse_cmc_hourly_selects_matching_cmc_id() -> None:
    payload = {
        "data": [
            {
                "id": 111,
                "name": "Rain Major",
                "symbol": "RAIN",
                "quotes": [
                    _quote("2024-01-01T00:00:00Z", 10.0, 11.0, 9.0, 10.5),
                    _quote("2024-01-01T01:00:00Z", 10.5, 12.0, 10.0, 11.0),
                ],
            },
            {
                "id": 999,
                "name": "Rain Clone",
                "symbol": "RAIN",
                "quotes": [
                    _quote("2024-01-01T00:00:00Z", 0.01, 0.02, 0.005, 0.015),
                    _quote("2024-01-01T01:00:00Z", 0.015, 0.03, 0.01, 0.02),
                ],
            },
        ]
    }
    rows = PriceHistoryFallbackClient._parse_cmc_hourly_quotes(payload, cmc_id=111)
    assert len(rows) == 2
    assert rows[0]["open"] == 10.0
    assert rows[1]["close"] == 11.0
    daily = aggregate_daily_bars_from_hourly(rows)
    assert len(daily) == 1
    assert daily[0]["open"] == 10.0
    assert daily[0]["high"] == 12.0
    assert daily[0]["low"] == 9.0
    assert daily[0]["close"] == 11.0


def test_legacy_merge_would_corrupt_daily_bar() -> None:
    """Document the pre-fix failure mode: concatenated quotes Frankenstein a day bar."""
    major = [
        {"ts": 1704067200, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 1.0},
        {"ts": 1704070800, "open": 10.5, "high": 12.0, "low": 10.0, "close": 11.0, "volume": 1.0},
    ]
    clone = [
        {"ts": 1704067200, "open": 0.01, "high": 0.02, "low": 0.005, "close": 0.015, "volume": 1.0},
        {"ts": 1704070800, "open": 0.015, "high": 0.03, "low": 0.01, "close": 0.02, "volume": 1.0},
    ]
    merged = sorted(major + clone, key=lambda r: r["ts"])
    daily = aggregate_daily_bars_from_hourly(merged)
    assert daily[0]["open"] == 10.0
    assert daily[0]["high"] == 12.0
    assert daily[0]["low"] == 0.005  # clone low poisons major range
    assert daily[0]["close"] == 0.02  # clone close wins as last row


def test_extract_cmc_prices_refuses_ambiguous_symbol_array() -> None:
    payload = {
        "data": {
            "RAIN": [
                {
                    "id": 111,
                    "quotes": [
                        {"timestamp": "2024-01-01T00:00:00Z", "quote": {"USD": {"price": 10.0}}},
                        {"timestamp": "2024-01-02T00:00:00Z", "quote": {"USD": {"price": 11.0}}},
                    ],
                },
                {
                    "id": 999,
                    "quotes": [
                        {"timestamp": "2024-01-01T00:00:00Z", "quote": {"USD": {"price": 0.01}}},
                        {"timestamp": "2024-01-02T00:00:00Z", "quote": {"USD": {"price": 0.02}}},
                    ],
                },
            ]
        }
    }
    assert PriceHistoryFallbackClient._extract_cmc_prices(payload, "RAIN") == []
    prices = PriceHistoryFallbackClient._extract_cmc_prices(payload, "RAIN", cmc_id=111)
    assert prices == [10.0, 11.0]
