"""
Exchange listing fetcher
Fetches listing data from various sources
"""

import requests
import time
from typing import List, Dict
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
        print("[INFO] Fetching Coinbase listings...")
        listings = []
        
        try:
            # Coinbase Pro products endpoint (public, no API key needed)
            url = "https://api.exchange.coinbase.com/products"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                products = response.json()
                for product in products:
                    # Skip delisted / non-tradable products (status may be "delisted")
                    if product.get('status') != 'online' or product.get('trading_disabled'):
                        continue
                    # Extract base currency (e.g., BTC-USD -> BTC)
                    base_currency = product['base_currency']
                    listings.append({
                        'symbol': base_currency,
                        'name': base_currency,  # Coinbase doesn't provide full names here
                        'source': 'coinbase_api'
                    })
                
                # Remove duplicates
                unique = {l['symbol']: l for l in listings}.values()
                print(f"   [OK] Found {len(unique)} unique assets on Coinbase")
                return list(unique)
            else:
                print(f"   [WARN] Coinbase API error: {response.status_code}")
                
        except Exception as e:
            print(f"   [WARN] Error fetching Coinbase listings: {e}")
        
        # Do not return hardcoded fallback here — update_all_exchanges decides
        # whether bootstrap seeding is safe (empty DB only).
        return []
    
    def fetch_kraken_listings(self) -> List[Dict]:
        """
        Fetch listings from Kraken using their public API
        """
        print("[INFO] Fetching Kraken listings...")
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
                    
                    print(f"   [OK] Found {len(listings)} unique assets on Kraken")
                    return listings
            else:
                print(f"   [WARN] Kraken API error: {response.status_code}")
                
        except Exception as e:
            print(f"   [WARN] Error fetching Kraken listings: {e}")
        
        return []
    
    def fetch_mexc_listings(self) -> List[Dict]:
        """
        Fetch listings from MEXC using their public API
        """
        print("[INFO] Fetching MEXC listings...")
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
                
                print(f"   [OK] Found {len(listings)} unique assets on MEXC")
                return listings
            else:
                print(f"   [WARN] MEXC API error: {response.status_code}")
                
        except Exception as e:
            print(f"   [WARN] Error fetching MEXC listings: {e}")
        
        return []
    
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
    
    def update_all_exchanges(self, target_exchanges: list[str] | None = None):
        """Update listings for configured target exchanges (inactive venues skipped)."""
        if target_exchanges is None:
            from config.settings import settings

            target_exchanges = settings.target_exchanges
        active = {str(ex).strip().lower() for ex in target_exchanges if str(ex).strip()}
        exchanges = {
            'coinbase': self.fetch_coinbase_listings,
            'kraken': self.fetch_kraken_listings,
            'mexc': self.fetch_mexc_listings
        }
        
        fallbacks = {
            'coinbase': self._get_coinbase_fallback,
            'kraken': self._get_kraken_fallback,
            'mexc': self._get_mexc_fallback,
        }

        for exchange, fetcher in exchanges.items():
            if exchange not in active:
                print(f"[SKIP] {exchange} not in TARGET_EXCHANGES")
                continue
            try:
                if self.db.needs_update(exchange):
                    listings = fetcher()
                    source = 'api'
                    if not listings:
                        existing = self.db.count_listings(exchange)
                        if existing > 0:
                            # Critical: never DELETE+replace a populated DB with ~30
                            # hardcoded symbols — that truncates the scan universe and
                            # stamps last_updated so needs_update stays false for 7 days.
                            print(
                                f"[WARN] {exchange} API returned no listings; "
                                f"keeping {existing} existing pairs (will retry next refresh)"
                            )
                            continue
                        listings = fallbacks[exchange]()
                        source = 'fallback'
                        print(
                            f"[WARN] {exchange} empty DB bootstrap fallback: "
                            f"{len(listings)} pairs"
                        )
                    if listings:
                        self.db.update_listings(exchange, listings, source=source)
                    time.sleep(2)  # Be nice to APIs
                else:
                    print(f"[SKIP] {exchange} listings are up to date")
            except Exception as e:
                print(f"[WARN] Error updating {exchange}: {e}")