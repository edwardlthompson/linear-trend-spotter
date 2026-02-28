"""CoinGecko API client with rate limiting - for volume data and price charts"""
import time
import requests
from typing import Optional, List, Dict
from collections import deque
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
    
    def __init__(self):
        self.session = requests.Session()
        self.rate_limiter = RateLimiter(10)  # 10 calls per minute
        self.logger = logging.getLogger('CoinGeckoClient')
    
    def _make_request(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[Dict]:
        """Make a rate-limited request with retries"""
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait()
                
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = (attempt + 1) * 30
                    self.logger.warning(f"Rate limited (429). Waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"API error {response.status_code}: {response.text[:200]}")
                    return None
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
            except Exception as e:
                self.logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
        
        return None
    
    def get_tickers(self, coin_id: str) -> Optional[Dict]:
        """Get tickers for a coin (exchange volume data)"""
        self.logger.info(f"Fetching tickers for {coin_id}")
        return self._make_request(f"{self.BASE_URL}/coins/{coin_id}/tickers")
    
    def get_market_chart(self, coin_id: str, days: int = 30) -> Optional[List]:
        """Get market chart data for uniformity calculation"""
        self.logger.info(f"Fetching market chart for {coin_id}")
        data = self._make_request(
            f"{self.BASE_URL}/coins/{coin_id}/market_chart",
            {'vs_currency': 'usd', 'days': days}
        )
        if data and 'prices' in data:
            prices = [p[1] for p in data['prices']]
            self.logger.info(f"✅ Got {len(prices)} price points for {coin_id}")
            self.logger.info(f"   First price: {prices[0]}, Last price: {prices[-1]}")
            return prices
        
        self.logger.error(f"❌ Failed to get price data for {coin_id}")
        return None