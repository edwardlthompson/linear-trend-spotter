"""
CoinMarketCap API client - Optimized for bulk gain data
Free tier: 10,000 calls/month, 30 calls/minute
"""

import requests
import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

class CoinMarketCapClient:
    """
    CoinMarketCap API client - perfect for bulk gain data
    One call gets ALL coins with 7d, 30d, 60d, 90d changes
    """
    
    BASE_URL = "https://pro-api.coinmarketcap.com/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.logger = logging.getLogger('CoinMarketCap')
        self.session.headers.update({
            'X-CMC_PRO_API_KEY': api_key,
            'Accept': 'application/json'
        })
        self.last_call = 0
        self.min_interval = 2  # 2 seconds between calls
    
    def _rate_limit(self):
        """Simple rate limiting"""
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()
    
    def get_all_coins_with_gains(self, limit: int = 5000) -> Optional[List[Dict]]:
        """
        Get ALL coins in ONE call with 7d, 30d, 60d, 90d gains
        Using max limit (5000) to get as many coins as possible
        """
        self._rate_limit()
        
        url = f"{self.BASE_URL}/cryptocurrency/listings/latest"
        params = {
            'start': '1',
            'limit': limit,  # CMC max is 5000
            'convert': 'USD'
        }
        
        self.logger.info(f"📡 Fetching {limit} coins with gains from CoinMarketCap...")
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                coins = data.get('data', [])
                self.logger.info(f"✅ Got {len(coins)} coins with gain data")
                return coins
            else:
                self.logger.error(f"❌ CMC API error: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error fetching from CMC: {e}")
            return None
    
    def extract_gains(self, coin_data: Dict) -> Dict:
        """
        Extract gain percentages from CMC data format
        Returns dict with 7d, 30d, 60d, 90d gains
        """
        quote = coin_data.get('quote', {}).get('USD', {})
        
        return {
            '7d': quote.get('percent_change_7d', 0),
            '30d': quote.get('percent_change_30d', 0),
            '60d': quote.get('percent_change_60d', 0),
            '90d': quote.get('percent_change_90d', 0),
        }
    
    def extract_coin_data(self, coin_data: Dict) -> Dict:
        """Extract basic coin data"""
        return {
            'symbol': coin_data.get('symbol', '').upper(),
            'name': coin_data.get('name', ''),
            'slug': coin_data.get('slug', ''),
            'rank': coin_data.get('cmc_rank', 0),
            'price': coin_data.get('quote', {}).get('USD', {}).get('price', 0),
            'volume_24h': coin_data.get('quote', {}).get('USD', {}).get('volume_24h', 0),
        }