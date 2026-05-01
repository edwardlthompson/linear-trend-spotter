"""Fallback price history providers for 30d daily series.

Primary data source remains CoinGecko in main flow.
This module provides provider fallbacks when CoinGecko is unavailable or incomplete.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import requests

from utils.provider_http_usage import record_cmc_http, record_polygon_http


class PriceHistoryFallbackClient:
    """Fallback chain: Polygon intraday/daily OHLCV, then CoinMarketCap OHLCV / closes."""

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

    def get_polygon_30d_hourly_ohlcv(self, symbol: str) -> Optional[list[dict[str, float]]]:
        """Get 30d hourly OHLCV from Polygon for non-Kraken intraday backtesting."""
        if not self.polygon_api_key:
            return None

        today = date.today()
        start = today - timedelta(days=30)
        url = f"https://api.polygon.io/v2/aggs/ticker/X:{symbol.upper()}USD/range/1/hour/{start.isoformat()}/{today.isoformat()}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.polygon_api_key,
        }

        for attempt in range(6):
            try:
                response = self.polygon_session.get(url, params=params, timeout=20)
                record_polygon_http(url)
                if response.status_code == 200:
                    payload = response.json()
                    results = payload.get("results", []) if isinstance(payload, dict) else []
                    if not isinstance(results, list) or not results:
                        return None

                    rows: list[dict[str, float]] = []
                    for row in results:
                        if not isinstance(row, dict):
                            continue
                        if any(row.get(key) is None for key in ("t", "o", "h", "l", "c")):
                            continue

                        ts_sec = int(float(row.get("t", 0)) / 1000)
                        rows.append(
                            {
                                "ts": ts_sec,
                                "open": float(row.get("o", 0)),
                                "high": float(row.get("h", 0)),
                                "low": float(row.get("l", 0)),
                                "close": float(row.get("c", 0)),
                                "volume": float(row.get("v", 0.0) or 0.0),
                            }
                        )

                    if len(rows) >= 600:
                        return rows
                    return None

                if response.status_code == 429 and attempt < 5:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = min(int(retry_after), 30)
                    else:
                        wait_time = min(3 * (attempt + 1), 20) + random.uniform(0, 1)
                    self.logger.warning(f"Polygon hourly 429 for {symbol}; waiting {wait_time:.1f}s")
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

    def get_polygon_30d_daily_ohlcv(self, symbol: str) -> Optional[list[dict[str, float]]]:
        """Daily OHLCV bars from Polygon (1/day aggregates), last ~30 days."""
        if not self.polygon_api_key:
            return None

        today = date.today()
        start = today - timedelta(days=35)
        url = (
            f"https://api.polygon.io/v2/aggs/ticker/X:{symbol.upper()}USD/range/1/day/"
            f"{start.isoformat()}/{today.isoformat()}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 5000,
            "apiKey": self.polygon_api_key,
        }

        try:
            response = self.polygon_session.get(url, params=params, timeout=20)
            record_polygon_http(url)
            if response.status_code != 200:
                return None
            payload = response.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(results, list) or not results:
                return None

            rows: list[dict[str, float]] = []
            for row in results:
                if not isinstance(row, dict):
                    continue
                if any(row.get(key) is None for key in ("t", "o", "h", "l", "c")):
                    continue
                ts_sec = int(float(row.get("t", 0)) / 1000)
                rows.append(
                    {
                        "ts": ts_sec,
                        "open": float(row.get("o", 0)),
                        "high": float(row.get("h", 0)),
                        "low": float(row.get("l", 0)),
                        "close": float(row.get("c", 0)),
                        "volume": float(row.get("v", 0.0) or 0.0),
                    }
                )

            if len(rows) >= 25:
                return rows
        except Exception as exc:
            self.logger.debug("Polygon daily OHLCV failed for %s: %s", symbol, exc)
        return None

    def get_cmc_hourly_ohlcv(self, symbol: str, days: int = 30) -> Optional[list[dict[str, float]]]:
        """Hourly OHLCV from CoinMarketCap (tertiary after CoinGecko/Polygon). Gated on API key."""
        if not self.cmc_api_key:
            return None

        symbol_u = str(symbol or "").strip().upper()
        if not symbol_u:
            return None

        count = min(2000, max(192, 24 * int(days) + 48))
        url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/ohlcv/historical"
        params: dict[str, Any] = {
            "symbol": symbol_u,
            "convert": "USD",
            "time_period": "hourly",
            "count": count,
        }

        for attempt in range(4):
            try:
                response = self.cmc_session.get(url, params=params, timeout=20)
                record_cmc_http(url)
                if response.status_code != 200:
                    if response.status_code == 429 and attempt < 3:
                        time.sleep(min(3 * (attempt + 1), 20) + random.uniform(0, 1))
                        continue
                    self.logger.debug(
                        "CMC hourly OHLCV HTTP %s for %s",
                        response.status_code,
                        symbol_u,
                    )
                    return None

                payload = response.json()
                rows = self._parse_cmc_hourly_quotes(payload)
                if rows and len(rows) >= 600:
                    return rows
                return None
            except Exception as exc:
                self.logger.debug("CMC hourly OHLCV error for %s: %s", symbol_u, exc)
                if attempt < 3:
                    time.sleep(min(2 * (attempt + 1), 15))
                    continue
                return None

        return None

    @staticmethod
    def _parse_cmc_hourly_quotes(payload: Any) -> list[dict[str, float]]:
        """Normalize CMC v2 OHLCV historical payloads into hourly row dicts."""
        if not isinstance(payload, dict):
            return []

        data = payload.get("data")
        quotes: list[dict[str, Any]] = []

        if isinstance(data, dict):
            q = data.get("quotes")
            if isinstance(q, list):
                quotes = [x for x in q if isinstance(x, dict)]
        elif isinstance(data, list):
            for block in data:
                if isinstance(block, dict):
                    q2 = block.get("quotes")
                    if isinstance(q2, list):
                        quotes.extend([x for x in q2 if isinstance(x, dict)])

        rows: list[dict[str, float]] = []
        for item in quotes:
            usd = item.get("quote", {}).get("USD", {}) if isinstance(item.get("quote"), dict) else {}
            if not isinstance(usd, dict):
                continue
            try:
                o = float(usd.get("open", 0) or 0)
                h = float(usd.get("high", 0) or 0)
                low = float(usd.get("low", 0) or 0)
                c = float(usd.get("close", 0) or 0)
                vol = float(usd.get("volume", 0) or 0)
            except (TypeError, ValueError):
                continue
            if o <= 0 or h <= 0 or low <= 0 or c <= 0:
                continue

            ts_raw = item.get("time_open") or item.get("timestamp")
            ts_sec = PriceHistoryFallbackClient._parse_cmc_ts_to_epoch(ts_raw)
            if ts_sec is None:
                continue

            rows.append(
                {
                    "ts": float(ts_sec),
                    "open": o,
                    "high": h,
                    "low": low,
                    "close": c,
                    "volume": vol,
                }
            )

        rows.sort(key=lambda r: r["ts"])
        return rows

    @staticmethod
    def _parse_cmc_ts_to_epoch(ts_raw: Any) -> Optional[int]:
        if ts_raw is None:
            return None
        if isinstance(ts_raw, (int, float)):
            v = float(ts_raw)
            return int(v / 1000) if v > 1e12 else int(v)
        text = str(ts_raw).strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            return None

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
                record_polygon_http(url)
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

    def get_cmc_daily_closes(self, symbol: str) -> Optional[list[float]]:
        """Public wrapper for last ~30d daily USD closes from CMC (used as tertiary daily OHLCV)."""
        return self._get_cmc_30d_daily(symbol)

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
                record_cmc_http(url)
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
