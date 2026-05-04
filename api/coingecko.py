"""CoinGecko API client with rate limiting - for volume data and price charts"""
import os
import time
import random
import json
import requests
import math
from typing import Optional, List, Dict, Any
import threading
import logging

from utils.coingecko_usage import record_coingecko_http

# CoinGecko `/coins/*/tickers` `exchange_ids` uses exchange **identifier** strings.
# Map config `TARGET_EXCHANGES` tokens to CG identifiers when they differ.
_COINGECKO_TICKER_EXCHANGE_IDS: dict[str, str] = {
    # CoinGecko still uses the legacy exchange id "gdax" for Coinbase Exchange.
    # Passing "coinbase" as exchange_ids does not filter tickers (returns mixed venues).
    "coinbase": "gdax",
    "mexc": "mxc",
}


def coingecko_ticker_exchange_ids_csv(target_exchanges: List[str]) -> Optional[str]:
    """Comma-separated CoinGecko exchange identifiers for ticker filtering."""
    parts: List[str] = []
    for raw in target_exchanges or []:
        key = str(raw or "").strip().lower()
        if not key:
            continue
        parts.append(_COINGECKO_TICKER_EXCHANGE_IDS.get(key, key))
    if not parts:
        return None
    return ",".join(parts)


class RateLimiter:
    """Simple rate limiter with queuing"""
    
    def __init__(self, calls_per_minute: int = 10):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call = 0
        self.lock = threading.Lock()
        self.logger = logging.getLogger('RateLimiter')
    
    def wait(self):
        """Wait if needed to respect rate limit"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                self.logger.debug(f"Rate limiting: waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)
            self.last_call = time.time()

class CoinGeckoClient:
    """CoinGecko API client - for volume data and price charts"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3"
    
    def __init__(self, calls_per_minute: int = 10):
        self.session = requests.Session()
        self.logger = logging.getLogger('CoinGeckoClient')
        headers = {'User-Agent': 'Linear-Trend-Spotter/1.0'}
        api_key = os.getenv('COINGECKO_API_KEY', '').strip()
        if api_key and api_key.startswith('CG-'):
            headers['x-cg-demo-api-key'] = api_key
            self.base_url = self.BASE_URL
            effective_cpm = max(1, min(calls_per_minute, 30))
        elif api_key:
            headers['x-cg-pro-api-key'] = api_key
            self.base_url = self.PRO_BASE_URL
            effective_cpm = max(1, min(calls_per_minute, 120))
        else:
            self.base_url = self.BASE_URL
            # Public API is shared; keep conservative cap for reliability.
            effective_cpm = max(1, min(calls_per_minute, 12))

        self.rate_limiter = RateLimiter(effective_cpm)
        self.session.headers.update(headers)
    
    def _make_request(
        self,
        url: str,
        params: dict = None,
        max_retries: int = 5,
        max_backoff_seconds: int = 120
    ) -> Optional[Dict]:
        """Make a rate-limited request with retries and adaptive backoff."""
        def _swap_host(input_url: str) -> str:
            if self.BASE_URL in input_url:
                return input_url.replace(self.BASE_URL, self.PRO_BASE_URL)
            if self.PRO_BASE_URL in input_url:
                return input_url.replace(self.PRO_BASE_URL, self.BASE_URL)
            return input_url

        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait()
                
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    record_coingecko_http(url)
                    return response.json()
                elif response.status_code == 429:
                    if attempt >= max_retries - 1:
                        self.logger.warning("Rate limited (429). Max retries reached; skipping request")
                        return None
                    retry_after = response.headers.get('Retry-After')
                    if retry_after and retry_after.isdigit():
                        wait_time = min(int(retry_after), max_backoff_seconds)
                    else:
                        # Exponential backoff with jitter: 15,30,60,120,120 (+0-2s)
                        wait_time = min(15 * (2 ** attempt), max_backoff_seconds)
                    wait_time += random.uniform(0, 2)
                    self.logger.warning(f"Rate limited (429). Waiting {wait_time:.1f}s before retry")
                    time.sleep(wait_time)
                    continue
                elif response.status_code in (408, 500, 503):
                    if attempt >= max_retries - 1:
                        self.logger.warning(f"Transient API error {response.status_code}. Max retries reached; skipping request")
                        return None
                    wait_time = min(5 * (2 ** attempt), 60) + random.uniform(0, 1)
                    self.logger.warning(f"Transient API error {response.status_code}. Retrying in {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    if response.status_code == 400:
                        try:
                            payload = json.loads(response.text)
                            error_code = payload.get('error_code')
                        except Exception:
                            error_code = None

                        if error_code in (10010, 10011) and attempt < max_retries - 1:
                            new_url = _swap_host(url)
                            if new_url != url:
                                self.logger.warning(f"CoinGecko host mismatch ({error_code}); retrying with alternate host")
                                url = new_url
                                continue

                    self.logger.error(f"API error {response.status_code}: {response.text[:200]}")
                    return None
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    wait_time = min(5 * (2 ** attempt), 60) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
            except Exception as e:
                self.logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    wait_time = min(5 * (2 ** attempt), 60) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
        
        return None
    
    def get_tickers(
        self,
        coin_id: str,
        *,
        exchange_ids: Optional[str] = None,
        page: Optional[int] = None,
        order: Optional[str] = None,
    ) -> Optional[Dict]:
        """Get tickers for a coin (exchange volume data).

        When ``exchange_ids`` is set (comma-separated CG exchange identifiers),
        CoinGecko returns only those venues—smaller payloads, same HTTP cost as
        an unfiltered call.

        Results are paginated (100 tickers per page). Pass ``page`` (1-based) to
        fetch later pages when merging volumes across many pairs.
        """
        self.logger.debug("Fetching tickers for %s", coin_id)
        params: dict[str, str] = {}
        if exchange_ids and str(exchange_ids).strip():
            params["exchange_ids"] = str(exchange_ids).strip()
        if page is not None and int(page) >= 1:
            params["page"] = str(int(page))
        if order and str(order).strip():
            params["order"] = str(order).strip()
        req_params: Optional[dict[str, str]] = params or None
        # Non-critical endpoint in this pipeline: fail fast to avoid scan stalls
        return self._make_request(
            f"{self.base_url}/coins/{coin_id}/tickers",
            params=req_params,
            max_retries=1,
            max_backoff_seconds=10,
        )

    def get_markets_rows_for_ids(
        self,
        coin_ids: List[str],
        *,
        chunk_size: int = 250,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch ``/coins/markets`` for explicit CoinGecko ids (one request per chunk).

        Used to batch-resolve ``COINGECKO_ID_ALIASES`` instead of one
        ``/coins/{id}`` call per symbol.
        """
        out: Dict[str, Dict[str, Any]] = {}
        normalized: List[str] = []
        seen: set[str] = set()
        for raw in coin_ids:
            cid = str(raw or "").strip().lower()
            if cid and cid not in seen:
                seen.add(cid)
                normalized.append(cid)
        if not normalized:
            return out

        cs = max(1, min(int(chunk_size), 250))
        for offset in range(0, len(normalized), cs):
            chunk = normalized[offset : offset + cs]
            params = {
                "vs_currency": "usd",
                "ids": ",".join(chunk),
                "per_page": len(chunk),
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "7d,30d",
            }
            payload = self._make_request(
                f"{self.base_url}/coins/markets",
                params=params,
                max_retries=3,
                max_backoff_seconds=30,
            )
            if not isinstance(payload, list):
                self.logger.warning(
                    "get_markets_rows_for_ids: expected list for chunk starting %s",
                    chunk[:1],
                )
                continue
            for row in payload:
                if isinstance(row, dict):
                    rid = str(row.get("id") or "").strip().lower()
                    if rid:
                        out[rid] = row
        return out

    def snapshot_from_markets_row(
        self,
        row: Dict[str, Any],
        *,
        symbol_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build the same structure as ``get_coin_market_snapshot`` from a /coins/markets row."""
        if not isinstance(row, dict):
            return None
        gecko_id = str(row.get("id", "")).strip().lower()
        if not gecko_id:
            return None
        gains = {
            "7d": float(row.get("price_change_percentage_7d_in_currency", 0) or 0),
            "30d": float(row.get("price_change_percentage_30d_in_currency", 0) or 0),
            "60d": 0.0,
            "90d": 0.0,
        }
        sym = (symbol_override or str(row.get("symbol", ""))).upper()
        info = {
            "symbol": sym,
            "name": str(row.get("name", "")).strip(),
            "slug": gecko_id,
            "gecko_id": gecko_id,
            "rank": int(row.get("market_cap_rank") or 999999),
            "price": float(row.get("current_price", 0) or 0),
            "volume_24h": float(row.get("total_volume", 0) or 0),
            "source_url": f"https://www.coingecko.com/en/coins/{gecko_id}",
        }
        return {"data": row, "gains": gains, "info": info}

    def get_top_coins_with_gains(self, limit: int = 4000, per_page: int = 250) -> Optional[List[Dict[str, Any]]]:
        """Fetch top-ranked market coins with 7d/30d gains and 24h volume.

        This method is optimized for scanner universe pre-filtering and intentionally
        avoids the strict low-throughput limiter used for per-coin endpoints.
        """
        try:
            target = max(1, int(limit))
            page_size = max(1, min(int(per_page), 250))
            pages = int(math.ceil(target / page_size))
            rows: List[Dict[str, Any]] = []

            for page in range(1, pages + 1):
                params = {
                    'vs_currency': 'usd',
                    'order': 'market_cap_desc',
                    'per_page': page_size,
                    'page': page,
                    'sparkline': 'false',
                    'price_change_percentage': '7d,30d',
                }

                page_data: Optional[List[Dict[str, Any]]] = None
                for attempt in range(3):
                    try:
                        response = self.session.get(
                            f"{self.base_url}/coins/markets",
                            params=params,
                            timeout=20,
                        )
                        if response.status_code == 200:
                            record_coingecko_http(response.url)
                            parsed = response.json()
                            if isinstance(parsed, list):
                                page_data = parsed
                                break
                            self.logger.error(f"CoinGecko /coins/markets invalid payload on page {page}")
                            return None

                        if response.status_code == 429:
                            retry_after = response.headers.get('Retry-After')
                            wait_time = float(retry_after) if retry_after and retry_after.isdigit() else 1.5 * (attempt + 1)
                            time.sleep(min(wait_time, 15.0))
                            continue

                        if response.status_code in (408, 500, 503):
                            time.sleep(1.0 * (attempt + 1))
                            continue

                        self.logger.error(f"CoinGecko /coins/markets error {response.status_code}: {response.text[:160]}")
                        return None
                    except Exception as request_error:
                        if attempt >= 2:
                            self.logger.error(f"CoinGecko /coins/markets request failed on page {page}: {request_error}")
                            return None
                        time.sleep(1.0 * (attempt + 1))

                if page_data is None:
                    return None

                rows.extend(page_data)
                if len(rows) >= target:
                    break
                time.sleep(0.12)

            return rows[:target]
        except Exception as e:
            self.logger.error(f"Error fetching top coins from CoinGecko: {e}")
            return None

    def get_coin_market_snapshot(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single CoinGecko coin snapshot with market data for filter checks."""
        normalized_id = str(coin_id or '').strip().lower()
        if not normalized_id:
            return None

        data = self._make_request(
            f"{self.base_url}/coins/{normalized_id}",
            {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'false',
                'developer_data': 'false',
                'sparkline': 'false',
            },
            max_retries=2,
            max_backoff_seconds=20,
        )
        if not isinstance(data, dict):
            return None

        market_data = data.get('market_data') or {}
        total_volume = market_data.get('total_volume') or {}
        current_price = market_data.get('current_price') or {}

        symbol = str(data.get('symbol', '')).upper()
        gains = {
            '7d': float(market_data.get('price_change_percentage_7d', 0) or 0),
            '30d': float(market_data.get('price_change_percentage_30d', 0) or 0),
            '60d': 0.0,
            '90d': 0.0,
        }
        info = {
            'symbol': symbol,
            'name': str(data.get('name', '')).strip(),
            'slug': normalized_id,
            'gecko_id': normalized_id,
            'rank': int(data.get('market_cap_rank') or 999999),
            'price': float(current_price.get('usd', 0) or 0),
            'volume_24h': float(total_volume.get('usd', 0) or 0),
            'source_url': f"https://www.coingecko.com/en/coins/{normalized_id}",
        }
        return {
            'data': data,
            'gains': gains,
            'info': info,
        }
    
    def get_market_chart(self, coin_id: str, days: int = 30, interval: str = 'daily') -> Optional[List]:
        """Get market chart data for uniformity calculation."""
        self.logger.info(f"Fetching market chart for {coin_id}")
        data = self._make_request(
            f"{self.base_url}/coins/{coin_id}/market_chart",
            {'vs_currency': 'usd', 'days': days, 'interval': interval}
        )
        if data and 'prices' in data:
            prices = [p[1] for p in data['prices']]
            self.logger.info(f"✅ Got {len(prices)} price points for {coin_id}")
            self.logger.info(f"   First price: {prices[0]}, Last price: {prices[-1]}")
            return prices
        
        self.logger.error(f"❌ Failed to get price data for {coin_id}")
        return None

    def get_ohlc(self, coin_id: str, days: int = 30) -> Optional[List[List[float]]]:
        """Get OHLC candles from CoinGecko for fallback backtesting paths."""
        self.logger.info(f"Fetching OHLC for {coin_id}")
        data: Any = self._make_request(
            f"{self.base_url}/coins/{coin_id}/ohlc",
            {'vs_currency': 'usd', 'days': days},
            max_retries=3,
            max_backoff_seconds=30,
        )

        if not isinstance(data, list):
            self.logger.error(f"❌ Failed to get OHLC data for {coin_id}")
            return None

        rows: List[List[float]] = []
        for row in data:
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                ts_ms = float(row[0])
                open_p = float(row[1])
                high_p = float(row[2])
                low_p = float(row[3])
                close_p = float(row[4])
            except (TypeError, ValueError):
                continue
            rows.append([ts_ms, open_p, high_p, low_p, close_p])

        if not rows:
            self.logger.error(f"❌ Empty OHLC payload for {coin_id}")
            return None

        self.logger.info(f"✅ Got {len(rows)} OHLC rows for {coin_id}")
        return rows

    def get_hourly_ohlcv(self, coin_id: str, days: int = 30) -> Optional[List[Dict[str, float]]]:
        """Build hourly OHLCV candles from CoinGecko market_chart hourly data."""
        data: Any = self._make_request(
            f"{self.base_url}/coins/{coin_id}/market_chart",
            {'vs_currency': 'usd', 'days': days},
            max_retries=3,
            max_backoff_seconds=30,
        )

        if not isinstance(data, dict):
            data = self._make_request(
                f"{self.base_url}/coins/{coin_id}/market_chart",
                {'vs_currency': 'usd', 'days': days, 'interval': 'hourly'},
                max_retries=1,
                max_backoff_seconds=10,
            )

        if not isinstance(data, dict):
            return None

        prices = data.get('prices', [])
        volumes = data.get('total_volumes', [])
        if not isinstance(prices, list) or len(prices) < 50:
            return None

        volume_by_hour: Dict[int, float] = {}
        if isinstance(volumes, list):
            for item in volumes:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                try:
                    ts_ms = float(item[0])
                    vol = float(item[1])
                except (TypeError, ValueError):
                    continue
                hour_sec = int(ts_ms // 1000 // 3600 * 3600)
                volume_by_hour[hour_sec] = vol

        price_by_hour: Dict[int, list[float]] = {}
        for item in prices:
            if not isinstance(item, list) or len(item) < 2:
                continue
            try:
                ts_ms = float(item[0])
                price = float(item[1])
            except (TypeError, ValueError):
                continue
            hour_sec = int(ts_ms // 1000 // 3600 * 3600)
            price_by_hour.setdefault(hour_sec, []).append(price)

        if not price_by_hour:
            return None

        rows: List[Dict[str, float]] = []
        for hour_sec in sorted(price_by_hour.keys()):
            bucket = price_by_hour[hour_sec]
            if not bucket:
                continue
            rows.append(
                {
                    'ts': float(hour_sec),
                    'open': float(bucket[0]),
                    'high': float(max(bucket)),
                    'low': float(min(bucket)),
                    'close': float(bucket[-1]),
                    'volume': float(volume_by_hour.get(hour_sec, 0.0)),
                }
            )

        if len(rows) < 300:
            return None

        return rows