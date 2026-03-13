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
        # Public API is shared; cap to a conservative upper bound for reliability
        self.rate_limiter = RateLimiter(max(1, min(calls_per_minute, 12)))
        self.logger = logging.getLogger('CoinGeckoClient')
        headers = {'User-Agent': 'Linear-Trend-Spotter/1.0'}
        api_key = os.getenv('COINGECKO_API_KEY', '').strip()
        if api_key and api_key.startswith('CG-'):
            headers['x-cg-demo-api-key'] = api_key
            self.base_url = self.BASE_URL
        elif api_key:
            headers['x-cg-pro-api-key'] = api_key
            self.base_url = self.PRO_BASE_URL
        else:
            self.base_url = self.BASE_URL
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
    
    def get_tickers(self, coin_id: str) -> Optional[Dict]:
        """Get tickers for a coin (exchange volume data)"""
        self.logger.info(f"Fetching tickers for {coin_id}")
        # Non-critical endpoint in this pipeline: fail fast to avoid scan stalls
        return self._make_request(
            f"{self.base_url}/coins/{coin_id}/tickers",
            max_retries=1,
            max_backoff_seconds=10
        )

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