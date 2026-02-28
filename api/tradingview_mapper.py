"""
TradingView Symbol Mapping Database
Checks MEXC, Kraken, and Coinbase in priority order
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading
import logging

class TradingViewMapper:
    """
    Maps coin symbols to TradingView/Chart-IMG format with exchange-specific rules
    Priority order: MEXC (USDT) → Kraken (USD) → Coinbase (USD)
    Only checks exchanges where coins have been verified to exist
    """
    
    # Exchange priority and quote preferences - UPDATED ORDER
    EXCHANGE_PRIORITY = [
        ('mexc', 'MEXC', 'USDT'),      # Most pairs, many meme coins
        ('kraken', 'KRAKEN', 'USD'),    # Good selection, established pairs
        ('coinbase', 'COINBASE', 'USD'), # Major exchange, fewer pairs
    ]
    
    # Special symbol mappings for each exchange
    SPECIAL_SYMBOLS = {
        'kraken': {
            'BTC': 'XBTUSD',  # Kraken uses XBT for Bitcoin
            'XBT': 'XBTUSD',  # Alternative
        },
        'coinbase': {
            'BTC': 'BTC-USD',  # Coinbase uses hyphen
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
        },
    }
    
    # Common meme coins and their most reliable exchanges
    MEME_COIN_MAPPINGS = {
        'PIPPIN': [('mexc', 'USDT')],
        'GOAT': [('mexc', 'USDT')],
        'FARTCOIN': [('mexc', 'USDT')],
        'SPX': [('mexc', 'USDT')],
        'POPCAT': [('mexc', 'USDT')],
        'MOG': [('mexc', 'USDT')],
        'BRETT': [('mexc', 'USDT')],
        'TURBO': [('mexc', 'USDT')],
        'COQ': [('mexc', 'USDT')],
        'ANDY': [('mexc', 'USDT')],
        'BOB': [('mexc', 'USDT')],
        'HARRIS': [('mexc', 'USDT')],
        'TRUMP': [('mexc', 'USDT')],
        'WIF': [('mexc', 'USDT')],
        'BONK': [('mexc', 'USDT')],
        'FLOKI': [('mexc', 'USDT')],
        'PEPE': [('mexc', 'USDT')],
        'SHIB': [('mexc', 'USDT')],
        'KAS': [('mexc', 'USDT')],
        'SUI': [('mexc', 'USDT')],
        'SEI': [('mexc', 'USDT')],
        'TIA': [('mexc', 'USDT')],
        'DYM': [('mexc', 'USDT')],
        'STRK': [('mexc', 'USDT')],
        'W': [('mexc', 'USDT')],
    }
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.logger = logging.getLogger('TradingViewMapper')
        self._local = threading.local()
        self._init_db()
        self._load_exchange_listings()
        self._load_meme_coin_mappings()
    
    def _get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tv_mappings (
                    coin_symbol TEXT,
                    exchange TEXT,
                    tv_symbol TEXT,
                    quote_currency TEXT,
                    is_active INTEGER DEFAULT 1,
                    PRIMARY KEY (coin_symbol, exchange, quote_currency)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS symbol_cache (
                    coin_symbol TEXT PRIMARY KEY,
                    tv_symbol TEXT
                )
            ''')
            
            conn.commit()
    
    def _format_tv_symbol(self, coin_symbol: str, exchange: str, quote: str) -> str:
        """Format TradingView symbol according to exchange rules"""
        exchange_upper = exchange.upper()
        
        # Check for special formatting
        if exchange in self.SPECIAL_SYMBOLS:
            special = self.SPECIAL_SYMBOLS[exchange]
            
            # Direct special mapping (like XBTUSD)
            if coin_symbol in special:
                special_symbol = special[coin_symbol]
                # If it already includes the exchange prefix, return as is
                if ':' in special_symbol:
                    return special_symbol
                return f"{exchange_upper}:{special_symbol}"
        
        # Exchange-specific formats
        if exchange == 'coinbase':
            # Coinbase uses hyphen format: COINBASE:BTC-USD
            return f"{exchange_upper}:{coin_symbol}-{quote}"
        elif exchange == 'kraken':
            # Kraken standard format: KRAKEN:ETHUSD
            return f"{exchange_upper}:{coin_symbol}{quote}"
        elif exchange == 'mexc':
            # MEXC standard format: MEXC:BTCUSDT
            return f"{exchange_upper}:{coin_symbol}{quote}"
        else:
            # Default format (should not reach here with our limited exchanges)
            return f"{exchange_upper}:{coin_symbol}{quote}"
    
    def _load_exchange_listings(self):
        """Pre-populate with common exchange pairs - prioritized by MEXC first"""
        # Common pairs by exchange - MEXC has the most
        exchange_pairs = {
            'mexc': [  # Most comprehensive - includes many pairs
                ('BTC', 'USDT'), ('ETH', 'USDT'), ('SOL', 'USDT'), ('XRP', 'USDT'),
                ('ADA', 'USDT'), ('DOGE', 'USDT'), ('DOT', 'USDT'), ('LINK', 'USDT'),
                ('MATIC', 'USDT'), ('AVAX', 'USDT'), ('UNI', 'USDT'), ('ALGO', 'USDT'),
                ('ATOM', 'USDT'), ('FIL', 'USDT'), ('ICP', 'USDT'), ('NEAR', 'USDT'),
                ('APT', 'USDT'), ('ARB', 'USDT'), ('OP', 'USDT'), ('WIF', 'USDT'),
                ('BONK', 'USDT'), ('FLOKI', 'USDT'), ('PEPE', 'USDT'), ('SHIB', 'USDT'),
                ('KAS', 'USDT'), ('SUI', 'USDT'), ('SEI', 'USDT'), ('TIA', 'USDT'),
                ('DYM', 'USDT'), ('STRK', 'USDT'), ('W', 'USDT'),
                # Additional meme coins
                ('PIPPIN', 'USDT'), ('GOAT', 'USDT'), ('FARTCOIN', 'USDT'), ('SPX', 'USDT'),
                ('POPCAT', 'USDT'), ('MOG', 'USDT'), ('BRETT', 'USDT'), ('TURBO', 'USDT'),
                ('COQ', 'USDT'), ('ANDY', 'USDT'), ('BOB', 'USDT'), ('HARRIS', 'USDT'),
                ('TRUMP', 'USDT'),
            ],
            'kraken': [  # Good selection of major pairs
                ('BTC', 'USD'), ('ETH', 'USD'), ('SOL', 'USD'), ('XRP', 'USD'),
                ('ADA', 'USD'), ('DOGE', 'USD'), ('DOT', 'USD'), ('LINK', 'USD'),
                ('MATIC', 'USD'), ('AVAX', 'USD'), ('UNI', 'USD'), ('ALGO', 'USD'),
                ('ATOM', 'USD'), ('FIL', 'USD'), ('SHIB', 'USD'), ('PEPE', 'USD'),
                ('KAS', 'USD'), ('SUI', 'USD'), ('SEI', 'USD'),
            ],
            'coinbase': [  # Fewer pairs but reliable for majors
                ('BTC', 'USD'), ('ETH', 'USD'), ('SOL', 'USD'), ('XRP', 'USD'),
                ('ADA', 'USD'), ('DOGE', 'USD'), ('DOT', 'USD'), ('LINK', 'USD'),
                ('MATIC', 'USD'), ('AVAX', 'USD'), ('UNI', 'USD'), ('ALGO', 'USD'),
                ('ATOM', 'USD'), ('FIL', 'USD'), ('ICP', 'USD'), ('NEAR', 'USD'),
                ('APT', 'USD'), ('ARB', 'USD'), ('OP', 'USD'), ('SHIB', 'USD'),
                ('PEPE', 'USD'), ('BONK', 'USD'), ('WIF', 'USD'),
            ],
        }
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for exchange, pairs in exchange_pairs.items():
                for base, quote in pairs:
                    tv_symbol = self._format_tv_symbol(base, exchange, quote)
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO tv_mappings 
                        (coin_symbol, exchange, tv_symbol, quote_currency, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (base, exchange, tv_symbol, quote))
            
            conn.commit()
            
        self.logger.info("✅ Loaded exchange listings - Priority: MEXC → Kraken → Coinbase")
    
    def _load_meme_coin_mappings(self):
        """Add mappings for meme coins - all point to MEXC first"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for coin, mappings in self.MEME_COIN_MAPPINGS.items():
                for exchange, quote in mappings:
                    tv_symbol = self._format_tv_symbol(coin, exchange, quote)
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO tv_mappings 
                        (coin_symbol, exchange, tv_symbol, quote_currency, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (coin, exchange, tv_symbol, quote))
            
            conn.commit()
        
        self.logger.info(f"✅ Loaded {len(self.MEME_COIN_MAPPINGS)} meme coin mappings (all default to MEXC)")
    
    def get_tv_symbol(self, coin_symbol: str, preferred_exchange: str = None) -> Optional[str]:
        """
        Get TradingView symbol checking MEXC → Kraken → Coinbase in priority order
        Only checks exchanges where coins have been verified to exist
        """
        coin_symbol = coin_symbol.upper()
        self.logger.info(f"🔍 Resolving TradingView symbol for {coin_symbol}")
        
        # Check cache first
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT tv_symbol FROM symbol_cache WHERE coin_symbol = ?', (coin_symbol,))
            cached = cursor.fetchone()
            if cached:
                self.logger.info(f"✅ Found cached symbol: {cached[0]}")
                return cached[0]
        
        # Try preferred exchange if specified
        if preferred_exchange:
            for exchange, ex_upper, quote in self.EXCHANGE_PRIORITY:
                if exchange == preferred_exchange:
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT tv_symbol FROM tv_mappings 
                            WHERE coin_symbol = ? AND exchange = ? AND quote_currency = ? AND is_active = 1
                        ''', (coin_symbol, exchange, quote))
                        result = cursor.fetchone()
                        if result:
                            self._cache_symbol(coin_symbol, result[0])
                            return result[0]
                    break
        
        # Try all exchanges in priority order: MEXC first, then Kraken, then Coinbase
        for exchange, ex_upper, quote in self.EXCHANGE_PRIORITY:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT tv_symbol FROM tv_mappings 
                    WHERE coin_symbol = ? AND exchange = ? AND quote_currency = ? AND is_active = 1
                ''', (coin_symbol, exchange, quote))
                result = cursor.fetchone()
                if result:
                    self.logger.info(f"✅ Found on {exchange.upper()}: {result[0]}")
                    self._cache_symbol(coin_symbol, result[0])
                    return result[0]
        
        self.logger.warning(f"❌ No TradingView symbol found for {coin_symbol} on any exchange")
        return None
    
    def _cache_symbol(self, coin_symbol: str, tv_symbol: str):
        """Cache a successful symbol lookup"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO symbol_cache (coin_symbol, tv_symbol)
                VALUES (?, ?)
            ''', (coin_symbol, tv_symbol))
            conn.commit()
    
    def add_custom_mapping(self, coin_symbol: str, exchange: str, quote: str = 'USDT'):
        """Add a custom mapping for a coin"""
        tv_symbol = self._format_tv_symbol(coin_symbol.upper(), exchange, quote)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tv_mappings 
                (coin_symbol, exchange, tv_symbol, quote_currency, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (coin_symbol.upper(), exchange, tv_symbol, quote))
            conn.commit()
        
        self.logger.info(f"✅ Added custom mapping: {coin_symbol} -> {tv_symbol}")
        return tv_symbol
    
    def get_exchange_for_symbol(self, tv_symbol: str) -> Optional[str]:
        """Extract exchange from TV symbol"""
        if ':' in tv_symbol:
            exchange = tv_symbol.split(':')[0].lower()
            return exchange
        return None
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn