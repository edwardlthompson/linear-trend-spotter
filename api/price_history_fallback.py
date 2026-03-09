"""Fallback price history providers for 30d daily series.

Primary data source remains CoinGecko in main flow.
This module provides provider fallbacks when CoinGecko is unavailable or incomplete.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, timedelta
from typing import Any, Optional

import requests


class PriceHistoryFallbackClient:
    """Fallback client chain for 30d daily prices: Polygon -> CoinMarketCap."""

    def __init__(self, polygon_api_key: str = "", cmc_api_key: str = ""):
        self.polygon_api_key = polygon_api_key or ""
        self.cmc_api_key = cmc_api_key or ""
        self.logger = logging.getLogger("PriceHistoryFallback")

        self.polygon_session = requests.Session()
        self.cmc_session = requests.Session()
        self.cmc_session.headers.update({
            "X-CMC_PRO_API_KEY": self.cmc_api_key,
            "Accept": "application/json",
        })

    def get_30d_prices(self, symbol: str) -> tuple[Optional[list[float]], str]:
        prices = self._get_polygon_30d_daily(symbol)
        if prices and len(prices) >= 25:
            return prices, "polygon"

        prices = self._get_cmc_30d_daily(symbol)
        if prices and len(prices) >= 25:
            return prices, "coinmarketcap"

        return None, "none"

    def _get_polygon_30d_daily(self, symbol: str) -> Optional[list[float]]:
        if not self.polygon_api_key:
            return None

        today = date.today()
        start = today - timedelta(days=30)
        url = f"https://api.polygon.io/v2/aggs/ticker/X:{symbol.upper()}USD/range/1/day/{start.isoformat()}/{today.isoformat()}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 5000,
            "apiKey": self.polygon_api_key,
        }

        for attempt in range(6):
            try:
                response = self.polygon_session.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    payload = response.json()
                    results = payload.get("results", []) if isinstance(payload, dict) else []
                    prices = [float(row.get("c", 0)) for row in results if isinstance(row, dict) and row.get("c") is not None]
                    if len(prices) >= 25:
                        return prices
                    return None

                if response.status_code == 429 and attempt < 5:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = min(int(retry_after), 30)
                    else:
                        wait_time = min(3 * (attempt + 1), 20) + random.uniform(0, 1)
                    self.logger.warning(f"Polygon 429 for {symbol}; waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue

                if response.status_code in (408, 500, 503) and attempt < 5:
                    wait_time = min(2 * (attempt + 1), 15) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue

                return None
            except Exception:
                if attempt < 5:
                    time.sleep(min(2 * (attempt + 1), 15))
                    continue
                return None

        return None

    def _get_cmc_30d_daily(self, symbol: str) -> Optional[list[float]]:
        if not self.cmc_api_key:
            return None

        end = date.today()
        start = end - timedelta(days=30)
        url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/historical"
        params = {
            "symbol": symbol.upper(),
            "time_start": f"{start.isoformat()}T00:00:00Z",
            "time_end": f"{end.isoformat()}T23:59:59Z",
            "interval": "daily",
            "count": 31,
            "convert": "USD",
        }

        for attempt in range(5):
            try:
                response = self.cmc_session.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    payload = response.json()
                    prices = self._extract_cmc_prices(payload, symbol.upper())
                    if len(prices) >= 25:
                        return prices
                    return None

                if response.status_code == 429 and attempt < 4:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = min(int(retry_after), 30)
                    else:
                        wait_time = min(3 * (attempt + 1), 20) + random.uniform(0, 1)
                    self.logger.warning(f"CMC 429 for {symbol}; waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue

                if response.status_code in (408, 500, 503) and attempt < 4:
                    wait_time = min(2 * (attempt + 1), 15) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue

                return None
            except Exception:
                if attempt < 4:
                    time.sleep(min(2 * (attempt + 1), 15))
                    continue
                return None

        return None

    @staticmethod
    def _extract_cmc_prices(payload: Any, symbol: str) -> list[float]:
        """Extract USD prices from multiple potential CMC response shapes."""
        if not isinstance(payload, dict):
            return []

        data = payload.get("data", {})
        records: list[dict] = []

        if isinstance(data, dict):
            symbol_data = data.get(symbol)
            if isinstance(symbol_data, list):
                for item in symbol_data:
                    if isinstance(item, dict):
                        records.append(item)
            elif isinstance(symbol_data, dict):
                quotes = symbol_data.get("quotes", [])
                if isinstance(quotes, list):
                    records.extend([q for q in quotes if isinstance(q, dict)])

            direct_quotes = data.get("quotes")
            if isinstance(direct_quotes, list):
                records.extend([q for q in direct_quotes if isinstance(q, dict)])

        prices_with_ts: list[tuple[str, float]] = []
        for record in records:
            quote = record.get("quote", {}) if isinstance(record, dict) else {}
            usd = quote.get("USD", {}) if isinstance(quote, dict) else {}
            price = usd.get("price") if isinstance(usd, dict) else None
            ts = record.get("timestamp") if isinstance(record, dict) else None
            if price is not None:
                prices_with_ts.append((str(ts or ""), float(price)))

        prices_with_ts.sort(key=lambda item: item[0])
        return [price for _, price in prices_with_ts]
