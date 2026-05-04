"""
CoinMarketCap API client - Optimized for bulk gain data
Verify limits on https://coinmarketcap.com/api/pricing/ (e.g. Basic free credits/month, RPM).
"""

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from utils.provider_http_usage import record_cmc_http


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
    
    def get_all_coins_with_gains(self, limit: int = 2500) -> Optional[List[Dict]]:
        """
        Get ALL coins in ONE call with 7d, 30d, 60d, 90d gains
        Default limit is 2500 to preserve free-plan API credits.
        """
        self._rate_limit()
        
        url = f"{self.BASE_URL}/cryptocurrency/listings/latest"
        params = {
            'start': '1',
            'limit': limit,  # CMC max is 5000, scanner default is 2500
            'convert': 'USD'
        }
        
        self.logger.info(f"📡 Fetching {limit} coins with gains from CoinMarketCap...")
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            record_cmc_http(url)

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

    def fetch_cryptocurrency_map_page(
        self,
        *,
        start: int = 1,
        limit: int = 5000,
        listing_status: str = "active",
    ) -> Optional[List[Dict]]:
        """One page of ``/v1/cryptocurrency/map`` for slug resolution (paginate externally)."""
        self._rate_limit()
        url = f"{self.BASE_URL}/cryptocurrency/map"
        params: Dict[str, Any] = {
            "listing_status": listing_status,
            "start": max(1, int(start)),
            "limit": min(5000, max(1, int(limit))),
        }
        try:
            response = self.session.get(url, params=params, timeout=60)
            record_cmc_http(url)
            if response.status_code != 200:
                self.logger.error("CMC map HTTP %s: %s", response.status_code, response.text[:200])
                return None
            payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list):
                return None
            return data
        except Exception as exc:
            self.logger.error("CMC map request failed: %s", exc)
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
        slug = str(coin_data.get('slug', '') or '').strip()
        slug_key = slug.lower()
        cmc_page = (
            f"https://coinmarketcap.com/currencies/{quote(slug_key, safe='')}/" if slug_key else ""
        )
        return {
            'symbol': coin_data.get('symbol', '').upper(),
            'name': coin_data.get('name', ''),
            'slug': slug,
            'rank': coin_data.get('cmc_rank', 0),
            'price': coin_data.get('quote', {}).get('USD', {}).get('price', 0),
            'volume_24h': coin_data.get('quote', {}).get('USD', {}).get('volume_24h', 0),
            'cmc_url': cmc_page,
            'source_url': cmc_page or None,
        }