"""
Optimized CoinGecko API client - with proper ID-based lookups and rate limit handling
"""

import requests
import time
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

class CoinGeckoOptimizedClient:
    """
    Optimized CoinGecko client that uses proper coin IDs
    """
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def __init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger('CoinGeckoOptimized')
        self.last_call = 0
        self.min_interval = 12  # 12 seconds between calls (5 per minute)
        self.daily_calls = 0
        self.last_reset = datetime.now()
        self.consecutive_failures = 0
    
    def _rate_limit(self):
        """Essential rate limiting with adaptive backoff"""
        now = time.time()
        elapsed = now - self.last_call
        
        # Base delay
        base_delay = self.min_interval
        
        # Add backoff if we've had failures
        if self.consecutive_failures > 0:
            backoff = min(2 ** self.consecutive_failures, 60)
            base_delay = max(base_delay, backoff)
        
        if elapsed < base_delay:
            sleep_time = base_delay - elapsed
            self.logger.debug(f"Rate limiting: waiting {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_call = time.time()
    
    def _make_request(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[Any]:
        """Make a rate-limited request with retries"""
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    self.consecutive_failures = 0
                    return response.json()
                elif response.status_code == 429:
                    self.consecutive_failures += 1
                    wait_time = (attempt + 1) * 60
                    self.logger.warning(f"Rate limited (429). Waiting {wait_time}s (attempt {attempt + 1})")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 404:
                    self.logger.warning(f"404 Not Found: {url}")
                    return None
                else:
                    self.logger.error(f"API error {response.status_code}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
        
        return None
    
    def get_market_chart(self, coin_id: str, days: int = 30) -> Optional[List[float]]:
        """
        Get historical price data using proper CoinGecko ID
        """
        if not coin_id:
            self.logger.warning("No coin_id provided")
            return None
        
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': days,
            'interval': 'daily'
        }
        
        self.logger.info(f"📡 Fetching price history for coin_id: {coin_id}")
        data = self._make_request(url, params)
        
        if data and 'prices' in data:
            prices = [p[1] for p in data['prices']]
            self.logger.info(f"✅ Got {len(prices)} price points")
            return prices
        
        return None
    
    def get_tickers(self, coin_id: str) -> Optional[Dict]:
        """
        Get ticker data for a coin (exchange volumes)
        """
        if not coin_id:
            self.logger.warning("No coin_id provided")
            return None
        
        url = f"{self.BASE_URL}/coins/{coin_id}/tickers"
        params = {
            'include_exchange_logo': 'false',
            'order': 'volume_desc'
        }
        
        self.logger.info(f"📡 Fetching tickers for coin_id: {coin_id}")
        data = self._make_request(url, params)
        
        if data:
            self.logger.info(f"✅ Got ticker data")
            return data
        
        return None
    
    def get_coin_info(self, coin_id: str) -> Optional[Dict]:
        """
        Get comprehensive coin info including market data
        """
        if not coin_id:
            self.logger.warning("No coin_id provided")
            return None
        
        url = f"{self.BASE_URL}/coins/{coin_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'true',
            'community_data': 'false',
            'developer_data': 'false'
        }
        
        self.logger.info(f"📡 Fetching coin info for coin_id: {coin_id}")
        data = self._make_request(url, params)
        
        if data:
            self.logger.info(f"✅ Got coin info")
            return data
        
        return None