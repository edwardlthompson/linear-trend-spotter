"""
DexPaprika API client - Free, no API key required
Provides token prices, 24h volume, and historical data
"""

import requests
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import time

class DexPaprikaClient:
    """
    DexPaprika API client - completely free, no API key needed
    Rate limit: 10,000 requests per day 
    """
    
    BASE_URL = "https://api.dexpaprika.com/v1"
    
    # Known token addresses for major coins [citation:7]
    KNOWN_TOKENS = {
        'ETH': {
            'network': 'ethereum',
            'address': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',  # WETH
            'name': 'Ethereum',
            'symbol': 'ETH'
        },
        'WETH': {
            'network': 'ethereum',
            'address': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
            'name': 'Wrapped Ethereum',
            'symbol': 'WETH'
        },
        'BTC': {
            'network': 'ethereum',
            'address': '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599',  # WBTC
            'name': 'Wrapped Bitcoin',
            'symbol': 'WBTC'
        },
        'WBTC': {
            'network': 'ethereum',
            'address': '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599',
            'name': 'Wrapped Bitcoin',
            'symbol': 'WBTC'
        },
        'SOL': {
            'network': 'solana',
            'address': 'So11111111111111111111111111111111111111112',  # Wrapped SOL
            'name': 'Wrapped Solana',
            'symbol': 'SOL'
        },
        'USDC': {
            'network': 'ethereum',
            'address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            'name': 'USD Coin',
            'symbol': 'USDC'
        },
        'USDT': {
            'network': 'ethereum',
            'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'name': 'Tether USD',
            'symbol': 'USDT'
        },
        'DAI': {
            'network': 'ethereum',
            'address': '0x6b175474e89094c44da98b954eedeac495271d0f',
            'name': 'Dai Stablecoin',
            'symbol': 'DAI'
        },
        'MATIC': {
            'network': 'polygon',
            'address': '0x0000000000000000000000000000000000001010',  # POL/MATIC
            'name': 'Polygon',
            'symbol': 'MATIC'
        },
        'AVAX': {
            'network': 'avalanche',
            'address': '0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7',  # WAVAX
            'name': 'Avalanche',
            'symbol': 'AVAX'
        }
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger('DexPaprika')
        self.session.headers.update({
            'User-Agent': 'Linear-Trend-Spotter/1.0'
        })
        self.daily_requests = 0
        self.last_reset = datetime.now()
    
    def _check_rate_limit(self):
        """Track daily rate limits (10k/day) """
        now = datetime.now()
        if now.date() > self.last_reset.date():
            self.daily_requests = 0
            self.last_reset = now
        
        if self.daily_requests >= 9500:
            self.logger.warning("⚠️ Approaching DexPaprika daily limit")
        
        self.daily_requests += 1
    
    def _make_request(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[Dict]:
        """Make a rate-limited request with retries"""
        self._check_rate_limit()
        
        for attempt in range(max_retries):
            try:
                time.sleep(0.2)
                
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    self.logger.warning(f"404 Not Found: {url}")
                    return None
                elif response.status_code == 429:
                    wait_time = (attempt + 1) * 5
                    self.logger.warning(f"Rate limited (429). Waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"API error {response.status_code}: {response.text[:200]}")
                    return None
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
            except Exception as e:
                self.logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
        
        return None
    
    def search_token(self, symbol: str) -> Optional[List[Dict]]:
        """
        Search for a token by symbol across all networks
        First checks known tokens, then falls back to API search
        """
        self.logger.info(f"🔍 Searching DexPaprika for {symbol}")
        
        # First check if it's a known token
        if symbol.upper() in self.KNOWN_TOKENS:
            known = self.KNOWN_TOKENS[symbol.upper()]
            self.logger.info(f"✅ Found {symbol} in known tokens on {known['network']}")
            return [{
                'network': known['network'],
                'address': known['address'],
                'name': known['name'],
                'symbol': known['symbol']
            }]
        
        # Fall back to API search
        url = f"{self.BASE_URL}/search"
        params = {'query': symbol}
        
        data = self._make_request(url, params)
        if not data:
            return None
        
        results = []
        if 'tokens' in data:
            for token in data['tokens']:
                if token.get('symbol', '').upper() == symbol.upper():
                    results.append({
                        'network': token.get('chain'),
                        'address': token.get('id'),
                        'name': token.get('name'),
                        'symbol': token.get('symbol')
                    })
        
        if 'pools' in data and not results:
            for pool in data['pools']:
                for token in pool.get('tokens', []):
                    if token.get('symbol', '').upper() == symbol.upper():
                        results.append({
                            'network': pool.get('chain'),
                            'address': token.get('id'),
                            'name': token.get('name'),
                            'symbol': token.get('symbol')
                        })
                        break
        
        if results:
            self.logger.info(f"✅ Found {len(results)} matches for {symbol}")
        else:
            self.logger.warning(f"⚠️ No matches found for {symbol}")
        
        return results if results else None
    
    def get_token_data(self, network: str, token_address: str) -> Optional[Dict]:
        """
        Get comprehensive token data including 24h volume and current price
        """
        url = f"{self.BASE_URL}/networks/{network}/tokens/{token_address}"
        
        data = self._make_request(url)
        if not data:
            return None
        
        result = {
            'price_usd': data.get('summary', {}).get('price_usd', 0),
            'liquidity_usd': data.get('summary', {}).get('liquidity_usd', 0),
            'volume_24h': data.get('summary', {}).get('day', {}).get('volume_usd', 0),
            'txns_24h': data.get('summary', {}).get('day', {}).get('txns', 0),
            'buys_24h': data.get('summary', {}).get('day', {}).get('buys', 0),
            'sells_24h': data.get('summary', {}).get('day', {}).get('sells', 0),
        }
        
        self.logger.info(f"✅ Got token data for {network}/{token_address[:10]}...")
        self.logger.info(f"   Price: ${result['price_usd']:.8f}, 24h Vol: ${result['volume_24h']:,.0f}")
        
        return result
    
    def get_token_price_history(self, network: str, token_address: str, days: int = 30) -> Optional[List[float]]:
        """
        Get historical price data for uniformity calculation
        Uses pool OHLCV data from the most liquid pool containing this token
        """
        # First, find pools containing this token
        pools_url = f"{self.BASE_URL}/networks/{network}/tokens/{token_address}/pools"
        pools_data = self._make_request(pools_url, {'limit': 5})
        
        if not pools_data or not pools_data.get('pools'):
            self.logger.warning(f"⚠️ No pools found for token on {network}")
            return None
        
        # Get the most liquid pool
        best_pool = pools_data['pools'][0]
        pool_address = best_pool['id']
        
        self.logger.info(f"   Using pool {pool_address[:10]}... for price history")
        
        # Get OHLCV data for this pool
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        ohlcv_url = f"{self.BASE_URL}/networks/{network}/pools/{pool_address}/ohlcv"
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d'),
            'interval': '1d',
            'limit': days
        }
        
        ohlcv_data = self._make_request(ohlcv_url, params)
        
        if not ohlcv_data or not ohlcv_data.get('items'):
            self.logger.warning(f"⚠️ No OHLCV data for pool")
            return None
        
        # Extract closing prices in order (oldest to newest)
        items = sorted(ohlcv_data['items'], key=lambda x: x['timestamp'])
        prices = [item['close'] for item in items]
        
        if len(prices) < 20:
            self.logger.warning(f"⚠️ Only {len(prices)} price points, need at least 20")
            return None
        
        self.logger.info(f"✅ Got {len(prices)} daily price points")
        return prices
    
    def meets_volume_threshold(self, token_data: Dict, min_volume: int) -> bool:
        """Check if token meets 24h volume requirement"""
        volume_24h = token_data.get('volume_24h', 0)
        return volume_24h >= min_volume

    def get_network_for_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Convenience method to find a token and get its data in one call
        Returns the first valid match with good volume
        """
        matches = self.search_token(symbol)
        if not matches:
            return None
        
        # Try each match until we find one with valid data
        for match in matches:
            token_data = self.get_token_data(match['network'], match['address'])
            if token_data and token_data.get('price_usd', 0) > 0:
                return {
                    **match,
                    **token_data
                }
        
        return None