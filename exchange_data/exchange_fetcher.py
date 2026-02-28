"""
Exchange listing fetcher
Fetches listing data from various sources
"""

import requests
import time
from typing import List, Dict, Optional
from datetime import datetime
from .exchange_db import ExchangeDatabase

class ExchangeFetcher:
    """
    Fetches exchange listings from multiple sources
    """
    
    def __init__(self, exchange_db: ExchangeDatabase):
        self.db = exchange_db
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Linear-Trend-Spotter/1.0'})
    
    def fetch_coinbase_listings(self) -> List[Dict]:
        """
        Fetch listings from Coinbase using their public API
        Coinbase has a free public endpoint for available pairs
        """
        print("📡 Fetching Coinbase listings...")
        listings = []
        
        try:
            # Coinbase Pro products endpoint (public, no API key needed)
            url = "https://api.exchange.coinbase.com/products"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                products = response.json()
                for product in products:
                    # Extract base currency (e.g., BTC-USD -> BTC)
                    base_currency = product['base_currency']
                    listings.append({
                        'symbol': base_currency,
                        'name': base_currency,  # Coinbase doesn't provide full names here
                        'source': 'coinbase_api'
                    })
                
                # Remove duplicates
                unique = {l['symbol']: l for l in listings}.values()
                print(f"   ✓ Found {len(unique)} unique assets on Coinbase")
                return list(unique)
            else:
                print(f"   ⚠️ Coinbase API error: {response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Error fetching Coinbase listings: {e}")
        
        # Fallback to hardcoded common listings if API fails
        return self._get_coinbase_fallback()
    
    def fetch_kraken_listings(self) -> List[Dict]:
        """
        Fetch listings from Kraken using their public API
        """
        print("📡 Fetching Kraken listings...")
        listings = []
        
        try:
            # Kraken asset pairs endpoint (public)
            url = "https://api.kraken.com/0/public/AssetPairs"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['error'] == []:
                    pairs = data['result']
                    seen = set()
                    
                    for pair_name, pair_data in pairs.items():
                        # Extract base currency
                        base = pair_data.get('base', '')
                        if base and base not in seen:
                            seen.add(base)
                            listings.append({
                                'symbol': base,
                                'name': base,
                                'source': 'kraken_api'
                            })
                    
                    print(f"   ✓ Found {len(listings)} unique assets on Kraken")
                    return listings
            else:
                print(f"   ⚠️ Kraken API error: {response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Error fetching Kraken listings: {e}")
        
        return self._get_kraken_fallback()
    
    def fetch_mexc_listings(self) -> List[Dict]:
        """
        Fetch listings from MEXC using their public API
        """
        print("📡 Fetching MEXC listings...")
        listings = []
        
        try:
            # MEXC ticker endpoint
            url = "https://api.mexc.com/api/v3/ticker/price"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                tickers = response.json()
                seen = set()
                
                for ticker in tickers:
                    # Extract base currency (e.g., BTCUSDT -> BTC)
                    symbol = ticker['symbol']
                    # Try to extract base currency (assumes USDT, BTC, ETH pairs)
                    for quote in ['USDT', 'BTC', 'ETH', 'USDC']:
                        if symbol.endswith(quote):
                            base = symbol[:-len(quote)]
                            if base and base not in seen:
                                seen.add(base)
                                listings.append({
                                    'symbol': base,
                                    'name': base,
                                    'source': 'mexc_api'
                                })
                            break
                
                print(f"   ✓ Found {len(listings)} unique assets on MEXC")
                return listings
            else:
                print(f"   ⚠️ MEXC API error: {response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Error fetching MEXC listings: {e}")
        
        return self._get_mexc_fallback()
    
    def _get_coinbase_fallback(self) -> List[Dict]:
        """Fallback list of common Coinbase assets"""
        common = [
            'BTC', 'ETH', 'USDT', 'USDC', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT',
            'LINK', 'MATIC', 'AVAX', 'UNI', 'ALGO', 'ATOM', 'FIL', 'ICP',
            'NEAR', 'APT', 'ARB', 'OP', 'LTC', 'BCH', 'ETC', 'XLM', 'VET',
            'EOS', 'TRX', 'SHIB', 'FLOKI', 'PEPE', 'BONK', 'WIF'
        ]
        return [{'symbol': s, 'name': s, 'source': 'fallback'} for s in common]
    
    def _get_kraken_fallback(self) -> List[Dict]:
        """Fallback list of common Kraken assets"""
        common = [
            'BTC', 'ETH', 'USDT', 'USDC', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT',
            'LINK', 'MATIC', 'AVAX', 'UNI', 'ALGO', 'ATOM', 'FIL', 'LTC',
            'BCH', 'ETC', 'XLM', 'TRX', 'SHIB', 'PEPE', 'KSM', 'DASH', 'ZEC'
        ]
        return [{'symbol': s, 'name': s, 'source': 'fallback'} for s in common]
    
    def _get_mexc_fallback(self) -> List[Dict]:
        """Fallback list of common MEXC assets"""
        common = [
            'BTC', 'ETH', 'USDT', 'USDC', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT',
            'LINK', 'MATIC', 'AVAX', 'UNI', 'ALGO', 'ATOM', 'FIL', 'LTC',
            'BCH', 'ETC', 'XLM', 'TRX', 'SHIB', 'PEPE', 'BONK', 'WIF',
            'FLOKI', 'KAS', 'SUI', 'SEI', 'TIA', 'DYM', 'STRK', 'W'
        ]
        return [{'symbol': s, 'name': s, 'source': 'fallback'} for s in common]
    
    def update_all_exchanges(self):
        """Update listings for all target exchanges"""
        exchanges = {
            'coinbase': self.fetch_coinbase_listings,
            'kraken': self.fetch_kraken_listings,
            'mexc': self.fetch_mexc_listings
        }
        
        for exchange, fetcher in exchanges.items():
            try:
                if self.db.needs_update(exchange):
                    listings = fetcher()
                    if listings:
                        self.db.update_listings(exchange, listings, source='api')
                    time.sleep(2)  # Be nice to APIs
                else:
                    print(f"⏭️  {exchange} listings are up to date")
            except Exception as e:
                print(f"⚠️ Error updating {exchange}: {e}")