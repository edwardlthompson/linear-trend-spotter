"""
CoinLore API client - Completely free, no rate limits, no API key required
Covers 14,000+ cryptocurrencies with real-time data
"""

import requests
import logging
import time
from typing import List, Dict, Optional, Any

class CoinLoreClient:
    """
    CoinLore API client - the ultimate free crypto data source
    No rate limits, no API key required, 14,000+ coins
    """
    
    BASE_URL = "https://api.coinlore.net/api"
    
    def __init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger('CoinLore')
        self.session.headers.update({
            'User-Agent': 'Linear-Trend-Spotter/1.0'
        })
        self.last_request = 0
    
    def _rate_limit(self):
        """Respect the 1 request per second recommendation"""
        now = time.time()
        elapsed = now - self.last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request = time.time()
    
    def _make_request(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[Any]:
        """Make a request with retries and rate limiting"""
        self._rate_limit()
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    try:
                        return response.json()
                    except requests.exceptions.JSONDecodeError as e:
                        self.logger.error(f"JSON decode error: {e}")
                        return None
                else:
                    self.logger.error(f"API error {response.status_code}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
        
        return None
    
    def get_all_coins(self, limit: int = 100) -> List[Dict]:
        """Get all coins (paginated, 100 per page)"""
        all_coins = []
        start = 0
        
        self.logger.info("📡 Fetching all coins from CoinLore...")
        
        while True:
            url = f"{self.BASE_URL}/tickers/"
            params = {
                'start': start,
                'limit': limit
            }
            
            data = self._make_request(url, params)
            if not data:
                break
            
            batch = data.get('data', [])
            if not batch:
                break
            
            all_coins.extend(batch)
            self.logger.info(f"   Got {len(batch)} coins (total: {len(all_coins)})")
            
            total_coins = data.get('info', {}).get('coins_num', 0)
            
            if len(all_coins) >= total_coins or len(batch) < limit:
                break
            
            start += limit
        
        self.logger.info(f"✅ Total coins fetched: {len(all_coins)}")
        return all_coins
    
    def get_coins_batch(self, coin_ids: List[str]) -> List[Dict]:
        """
        Get multiple coins by ID in a SINGLE request
        Uses /ticker/?id=id1,id2,id3 endpoint
        """
        if not coin_ids:
            return []
        
        valid_ids = [str(id).strip() for id in coin_ids if id is not None and str(id).strip()]
        
        if not valid_ids:
            return []
        
        max_ids_per_request = 100
        all_results = []
        
        for i in range(0, len(valid_ids), max_ids_per_request):
            batch_ids = valid_ids[i:i+max_ids_per_request]
            ids_param = ','.join(batch_ids)
            
            self.logger.info(f"📡 Batch fetching {len(batch_ids)} coins")
            
            url = f"{self.BASE_URL}/ticker/"
            params = {'id': ids_param}
            
            data = self._make_request(url, params)
            
            if data and isinstance(data, list):
                all_results.extend(data)
        
        return all_results
    
    def get_coin_by_id(self, coin_id: str) -> Optional[Dict]:
        """Get single coin by ID"""
        if not coin_id:
            return None
        
        url = f"{self.BASE_URL}/ticker/"
        params = {'id': coin_id}
        
        data = self._make_request(url, params)
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    
    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Safely convert a value to float"""
        if value is None:
            return default
        
        try:
            str_val = str(value).strip()
            cleaned = ''
            for char in str_val:
                if char.isdigit() or char == '.' or char == '-' or char == 'e' or char == 'E':
                    cleaned += char
                elif char == ',':
                    continue
                else:
                    break
            
            if cleaned and cleaned != '-' and cleaned != '.':
                return float(cleaned)
            return default
        except (ValueError, TypeError):
            return default
    
    def extract_coin_data(self, coin: Dict) -> Dict:
        """Extract standardized data from CoinLore format"""
        return {
            'symbol': str(coin.get('symbol', '')).upper(),
            'coin_id': str(coin.get('id', '')),
            'name': str(coin.get('name', '')),
            'rank': self._safe_int(coin.get('rank', 0)),
            'price_usd': self._safe_float(coin.get('price_usd', 0)),
            'volume_24h': self._safe_float(coin.get('volume24', 0)),
            'market_cap': self._safe_float(coin.get('market_cap_usd', 0)),
            'percent_change_1h': self._safe_float(coin.get('percent_change_1h', 0)),
            'percent_change_24h': self._safe_float(coin.get('percent_change_24h', 0)),
            'percent_change_7d': self._safe_float(coin.get('percent_change_7d', 0)),
        }
    
    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert to int"""
        try:
            return int(self._safe_float(value, default))
        except (ValueError, TypeError):
            return default
    
    def extract_gains(self, coin: Dict) -> Dict:
        """Extract all gain percentages from coin data"""
        return {
            '1h': self._safe_float(coin.get('percent_change_1h', 0)),
            '24h': self._safe_float(coin.get('percent_change_24h', 0)),
            '7d': self._safe_float(coin.get('percent_change_7d', 0)),
            '14d': 0,  # Not provided by CoinLore, will calculate from price history
            '30d': 0,  # Not provided by CoinLore, will calculate from price history
        }
    
    def meets_volume_threshold(self, coin: Dict, min_volume: int) -> bool:
        """Check if coin meets minimum volume requirement"""
        volume = self._safe_float(coin.get('volume24', 0))
        return volume >= min_volume