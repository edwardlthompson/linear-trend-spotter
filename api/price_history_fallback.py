"""Fallback price history providers for 30d daily series.

Primary data source remains CoinGecko in main flow.
This module provides provider fallbacks when CoinGecko is unavailable or incomplete.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import requests

from utils.provider_circuit import ProviderCallCircuit
from utils.provider_http_usage import record_cmc_http, record_polygon_http
from utils.provider_rate_limit import MinIntervalGate, backoff_seconds_for_attempt


class PriceHistoryFallbackClient:
    """Fallback chain: Polygon intraday/daily OHLCV, then CoinMarketCap OHLCV / closes."""

    def __init__(
        self,
        polygon_api_key: str = "",
        cmc_api_key: str = "",
        *,
        cmc_rate_gate: MinIntervalGate | None = None,
        polygon_rate_gate: MinIntervalGate | None = None,
        cmc_calls_per_minute: int = 30,
        polygon_calls_per_minute: int = 5,
        polygon_circuit: ProviderCallCircuit | None = None,
        cmc_circuit: ProviderCallCircuit | None = None,
    ):
        self.polygon_api_key = polygon_api_key or ""
        self.cmc_api_key = cmc_api_key or ""
        self.logger = logging.getLogger("PriceHistoryFallback")

        self._cmc_gate = cmc_rate_gate if cmc_rate_gate is not None else MinIntervalGate(cmc_calls_per_minute)
        self._polygon_gate = polygon_rate_gate if polygon_rate_gate is not None else MinIntervalGate(
            polygon_calls_per_minute
        )

        self.polygon_session = requests.Session()
        self.cmc_session = requests.Session()
        self.cmc_session.headers.update(
            {
                "X-CMC_PRO_API_KEY": self.cmc_api_key,
                "Accept": "application/json",
            }
        )
        self._polygon_circuit = polygon_circuit
        self._cmc_circuit = cmc_circuit

    def _polygon_http_get(
        self,
        url: str,
        params: dict[str, Any],
        *,
        timeout: float,
        max_retries: int = 6,
        label: str = "",
    ) -> Optional[requests.Response]:
        """Paced Polygon GET with 429 / transient backoff."""
        if self._polygon_circuit and not self._polygon_circuit.allow():
            return None
        for attempt in range(max_retries):
            self._polygon_gate.wait()
            try:
                response = self.polygon_session.get(url, params=params, timeout=timeout)
                record_polygon_http(url)
                if response.status_code == 200:
                    if self._polygon_circuit:
                        self._polygon_circuit.record_success()
                    return response
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_s = backoff_seconds_for_attempt(attempt, response=response)
                    self.logger.warning("Polygon rate limited (429)%s; sleeping %.1fs", label, wait_s)
                    time.sleep(wait_s)
                    continue
                if response.status_code in (408, 500, 502, 503, 504) and attempt < max_retries - 1:
                    wait_s = min(5 * (2**attempt), 60) + 0.25
                    self.logger.warning("Polygon HTTP %s%s; retry in %.1fs", response.status_code, label, wait_s)
                    time.sleep(wait_s)
                    continue
                if self._polygon_circuit and response.status_code != 200:
                    self._polygon_circuit.record_failure()
                return response
            except requests.exceptions.Timeout:
                if attempt >= max_retries - 1:
                    self.logger.warning("Polygon timeout%s (giving up)", label)
                    if self._polygon_circuit:
                        self._polygon_circuit.record_failure()
                    return None
                time.sleep(min(5 * (2**attempt), 45))
            except Exception as exc:
                self.logger.debug("Polygon request error%s: %s", label, exc)
                if attempt >= max_retries - 1:
                    if self._polygon_circuit:
                        self._polygon_circuit.record_failure()
                    return None
                time.sleep(min(3 * (2**attempt), 30))
        if self._polygon_circuit:
            self._polygon_circuit.record_failure()
        return None

    def _cmc_http_get(
        self,
        url: str,
        params: dict[str, Any],
        *,
        timeout: float,
        max_retries: int = 6,
        label: str = "",
    ) -> Optional[requests.Response]:
        """Paced CMC GET with 429 / transient backoff (shares gate with ``CoinMarketCapClient`` when injected)."""
        if self._cmc_circuit and not self._cmc_circuit.allow():
            return None
        for attempt in range(max_retries):
            self._cmc_gate.wait()
            try:
                response = self.cmc_session.get(url, params=params, timeout=timeout)
                record_cmc_http(url)
                if response.status_code == 200:
                    if self._cmc_circuit:
                        self._cmc_circuit.record_success()
                    return response
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_s = backoff_seconds_for_attempt(attempt, response=response)
                    self.logger.warning("CMC rate limited (429)%s; sleeping %.1fs", label, wait_s)
                    time.sleep(wait_s)
                    continue
                if response.status_code in (408, 500, 502, 503, 504) and attempt < max_retries - 1:
                    wait_s = min(5 * (2**attempt), 60) + 0.25
                    self.logger.warning("CMC HTTP %s%s; retry in %.1fs", response.status_code, label, wait_s)
                    time.sleep(wait_s)
                    continue
                if self._cmc_circuit and response.status_code != 200:
                    self._cmc_circuit.record_failure()
                return response
            except requests.exceptions.Timeout:
                if attempt >= max_retries - 1:
                    self.logger.warning("CMC timeout%s (giving up)", label)
                    if self._cmc_circuit:
                        self._cmc_circuit.record_failure()
                    return None
                time.sleep(min(5 * (2**attempt), 45))
            except Exception as exc:
                self.logger.debug("CMC request error%s: %s", label, exc)
                if attempt >= max_retries - 1:
                    if self._cmc_circuit:
                        self._cmc_circuit.record_failure()
                    return None
                time.sleep(min(3 * (2**attempt), 30))
        if self._cmc_circuit:
            self._cmc_circuit.record_failure()
        return None

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
        params: dict[str, Any] = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.polygon_api_key,
        }

        response = self._polygon_http_get(url, params, timeout=20.0, label=f" hourly {symbol}")
        if response is None or response.status_code != 200:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
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

        response = self._polygon_http_get(url, params, timeout=20.0, label=f" daily_ohlcv {symbol}")
        if response is None or response.status_code != 200:
            return None
        try:
            payload = response.json()
        except Exception as exc:
            self.logger.debug("Polygon daily OHLCV JSON for %s: %s", symbol, exc)
            return None
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
        return None

    def get_cmc_hourly_ohlcv(
        self,
        symbol: str,
        days: int = 30,
        *,
        cmc_id: int | None = None,
    ) -> Optional[list[dict[str, float]]]:
        """Hourly OHLCV from CoinMarketCap (tertiary after CoinGecko/Polygon). Gated on API key.

        Prefer ``cmc_id`` whenever available. Querying by ticker alone can return multiple
        CMC assets; those must not be merged into one series.
        """
        if not self.cmc_api_key:
            return None

        symbol_u = str(symbol or "").strip().upper()
        resolved_id: int | None = None
        if cmc_id is not None:
            try:
                resolved_id = int(cmc_id)
            except (TypeError, ValueError):
                resolved_id = None
        if resolved_id is None and not symbol_u:
            return None

        count = min(2000, max(192, 24 * int(days) + 48))
        url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/ohlcv/historical"
        params: dict[str, Any] = {
            "convert": "USD",
            "time_period": "hourly",
            "count": count,
        }
        label = symbol_u or f"id:{resolved_id}"
        if resolved_id is not None:
            params["id"] = resolved_id
        else:
            params["symbol"] = symbol_u

        response = self._cmc_http_get(url, params, timeout=20.0, label=f" OHLCV {label}")
        if response is None or response.status_code != 200:
            self.logger.debug(
                "CMC hourly OHLCV HTTP for %s status=%s",
                label,
                getattr(response, "status_code", None),
            )
            return None
        try:
            payload = response.json()
        except Exception as exc:
            self.logger.debug("CMC hourly OHLCV JSON for %s: %s", label, exc)
            return None
        rows = self._parse_cmc_hourly_quotes(payload, cmc_id=resolved_id)
        if rows and len(rows) >= 600:
            return rows
        return None

    @staticmethod
    def _parse_cmc_hourly_quotes(
        payload: Any,
        *,
        cmc_id: int | None = None,
    ) -> list[dict[str, float]]:
        """Normalize CMC v2 OHLCV historical payloads into hourly row dicts.

        When ``data`` is a list (symbol collision), keep a single block: the matching
        ``cmc_id`` if provided, otherwise refuse (empty) — never concatenate series.
        """
        if not isinstance(payload, dict):
            return []

        data = payload.get("data")
        quotes: list[dict[str, Any]] = []

        if isinstance(data, dict):
            q = data.get("quotes")
            if isinstance(q, list):
                quotes = [x for x in q if isinstance(x, dict)]
        elif isinstance(data, list):
            blocks = [b for b in data if isinstance(b, dict)]
            chosen: dict[str, Any] | None = None
            if cmc_id is not None:
                for block in blocks:
                    try:
                        if int(block.get("id")) == int(cmc_id):
                            chosen = block
                            break
                    except (TypeError, ValueError):
                        continue
            elif len(blocks) == 1:
                chosen = blocks[0]
            else:
                # Ambiguous ticker match — do not Frankenstein OHLCV from multiple assets.
                return []
            if chosen is None:
                return []
            q2 = chosen.get("quotes")
            if isinstance(q2, list):
                quotes = [x for x in q2 if isinstance(x, dict)]

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

        response = self._polygon_http_get(url, params, timeout=15.0, label=f" daily_closes {symbol}")
        if response is None or response.status_code != 200:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        results = payload.get("results", []) if isinstance(payload, dict) else []
        prices = [float(row.get("c", 0)) for row in results if isinstance(row, dict) and row.get("c") is not None]
        if len(prices) >= 25:
            return prices
        return None

    def get_cmc_daily_closes(
        self,
        symbol: str,
        *,
        cmc_id: int | None = None,
    ) -> Optional[list[float]]:
        """Public wrapper for last ~30d daily USD closes from CMC (used as tertiary daily OHLCV)."""
        return self._get_cmc_30d_daily(symbol, cmc_id=cmc_id)

    def _get_cmc_30d_daily(
        self,
        symbol: str,
        *,
        cmc_id: int | None = None,
    ) -> Optional[list[float]]:
        if not self.cmc_api_key:
            return None

        symbol_u = str(symbol or "").strip().upper()
        resolved_id: int | None = None
        if cmc_id is not None:
            try:
                resolved_id = int(cmc_id)
            except (TypeError, ValueError):
                resolved_id = None
        if resolved_id is None and not symbol_u:
            return None

        end = date.today()
        start = end - timedelta(days=30)
        url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/historical"
        params: dict[str, Any] = {
            "time_start": f"{start.isoformat()}T00:00:00Z",
            "time_end": f"{end.isoformat()}T23:59:59Z",
            "interval": "daily",
            "count": 31,
            "convert": "USD",
        }
        label = symbol_u or f"id:{resolved_id}"
        if resolved_id is not None:
            params["id"] = resolved_id
        else:
            params["symbol"] = symbol_u

        response = self._cmc_http_get(url, params, timeout=15.0, label=f" quotes_hist {label}")
        if response is None or response.status_code != 200:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        prices = self._extract_cmc_prices(payload, symbol_u, cmc_id=resolved_id)
        if len(prices) >= 25:
            return prices
        return None

    @staticmethod
    def _extract_cmc_prices(
        payload: Any,
        symbol: str,
        *,
        cmc_id: int | None = None,
    ) -> list[float]:
        """Extract USD prices from multiple potential CMC response shapes.

        Ambiguous symbol arrays (multiple CMC ids) are refused unless ``cmc_id`` selects one.
        """
        if not isinstance(payload, dict):
            return []

        data = payload.get("data", {})
        records: list[dict] = []

        if isinstance(data, dict):
            symbol_data = data.get(symbol) if symbol else None
            if isinstance(symbol_data, list):
                blocks = [item for item in symbol_data if isinstance(item, dict)]
                chosen: dict | None = None
                if cmc_id is not None:
                    for block in blocks:
                        try:
                            if int(block.get("id")) == int(cmc_id):
                                chosen = block
                                break
                        except (TypeError, ValueError):
                            continue
                elif len(blocks) == 1:
                    chosen = blocks[0]
                else:
                    return []
                if chosen is None:
                    return []
                nested = chosen.get("quotes")
                if isinstance(nested, list):
                    records.extend([q for q in nested if isinstance(q, dict)])
                else:
                    # Some shapes put quote/price on the coin object itself.
                    records.append(chosen)
            elif isinstance(symbol_data, dict):
                quotes = symbol_data.get("quotes", [])
                if isinstance(quotes, list):
                    records.extend([q for q in quotes if isinstance(q, dict)])

            direct_quotes = data.get("quotes")
            if isinstance(direct_quotes, list):
                records.extend([q for q in direct_quotes if isinstance(q, dict)])
        elif isinstance(data, list):
            blocks = [b for b in data if isinstance(b, dict)]
            chosen_list: dict | None = None
            if cmc_id is not None:
                for block in blocks:
                    try:
                        if int(block.get("id")) == int(cmc_id):
                            chosen_list = block
                            break
                    except (TypeError, ValueError):
                        continue
            elif len(blocks) == 1:
                chosen_list = blocks[0]
            else:
                return []
            if chosen_list is None:
                return []
            nested = chosen_list.get("quotes")
            if isinstance(nested, list):
                records.extend([q for q in nested if isinstance(q, dict)])

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
