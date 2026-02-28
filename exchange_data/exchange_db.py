"""
Exchange listing database
Stores which coins are listed on which exchanges
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import threading

class ExchangeDatabase:
    """
    Database of coin listings on various exchanges
    Provides fast lookup without API calls
    """
    
    # How often to refresh listings (7 days)
    REFRESH_DAYS = 7
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
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
            
            # Main listings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exchange_listings (
                    exchange TEXT,
                    symbol TEXT,
                    name TEXT,
                    coingecko_id TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    source TEXT,
                    PRIMARY KEY (exchange, symbol)
                )
            ''')
            
            # Exchange metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exchange_metadata (
                    exchange TEXT PRIMARY KEY,
                    last_updated TEXT,
                    total_pairs INTEGER,
                    source TEXT
                )
            ''')
            
            # Cache for quick lookups
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS listing_cache (
                    symbol TEXT,
                    exchange TEXT,
                    is_listed INTEGER,
                    last_checked TEXT,
                    PRIMARY KEY (symbol, exchange)
                )
            ''')
            
            conn.commit()
    
    def is_listed(self, symbol: str, exchange: str) -> bool:
        """
        Check if a coin is listed on an exchange
        
        Args:
            symbol: Coin symbol (e.g., 'BTC')
            exchange: Exchange name (e.g., 'coinbase')
            
        Returns:
            True if listed, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_listed FROM listing_cache
                WHERE symbol = ? AND exchange = ?
            ''', (symbol.upper(), exchange))
            
            result = cursor.fetchone()
            if result:
                return bool(result[0])
            
            # If not in cache, check listings table
            cursor.execute('''
                SELECT COUNT(*) FROM exchange_listings
                WHERE exchange = ? AND symbol = ?
            ''', (exchange, symbol.upper()))
            
            count = cursor.fetchone()[0]
            is_listed = count > 0
            
            # Cache the result
            cursor.execute('''
                INSERT OR REPLACE INTO listing_cache (symbol, exchange, is_listed, last_checked)
                VALUES (?, ?, ?, ?)
            ''', (symbol.upper(), exchange, 1 if is_listed else 0, datetime.now().isoformat()))
            
            conn.commit()
            return is_listed
    
    def batch_check_listings(self, symbols: List[str], exchange: str) -> Dict[str, bool]:
        """
        Check multiple coins against an exchange in one batch
        
        Args:
            symbols: List of coin symbols
            exchange: Exchange name
            
        Returns:
            Dictionary of {symbol: is_listed}
        """
        results = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create temporary table for the symbols
            cursor.execute('CREATE TEMP TABLE IF NOT EXISTS temp_symbols (symbol TEXT)')
            cursor.execute('DELETE FROM temp_symbols')
            
            for symbol in symbols:
                cursor.execute('INSERT INTO temp_symbols VALUES (?)', (symbol.upper(),))
            
            # Join with listings
            cursor.execute('''
                SELECT t.symbol, CASE WHEN l.exchange IS NOT NULL THEN 1 ELSE 0 END as listed
                FROM temp_symbols t
                LEFT JOIN exchange_listings l ON l.exchange = ? AND l.symbol = t.symbol
            ''', (exchange,))
            
            for row in cursor.fetchall():
                results[row[0]] = bool(row[1])
            
            # Update cache for all checked symbols
            now = datetime.now().isoformat()
            for symbol, listed in results.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO listing_cache (symbol, exchange, is_listed, last_checked)
                    VALUES (?, ?, ?, ?)
                ''', (symbol, exchange, 1 if listed else 0, now))
            
            conn.commit()
        
        return results
    
    def update_listings(self, exchange: str, listings: List[Dict], source: str = 'api'):
        """
        Update listings for an exchange
        
        Args:
            exchange: Exchange name
            listings: List of dicts with 'symbol' and optionally 'name', 'coingecko_id'
            source: Source of the data ('coinbase_api', 'kraken_api', 'coingecko', etc.)
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Clear old listings for this exchange
            cursor.execute('DELETE FROM exchange_listings WHERE exchange = ?', (exchange,))
            
            # Insert new listings
            for listing in listings:
                cursor.execute('''
                    INSERT INTO exchange_listings (exchange, symbol, name, coingecko_id, first_seen, last_seen, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    exchange,
                    listing['symbol'].upper(),
                    listing.get('name', ''),
                    listing.get('coingecko_id', ''),
                    now,
                    now,
                    source
                ))
            
            # Update exchange metadata
            cursor.execute('''
                INSERT OR REPLACE INTO exchange_metadata (exchange, last_updated, total_pairs, source)
                VALUES (?, ?, ?, ?)
            ''', (exchange, now, len(listings), source))
            
            # Clear cache for this exchange (will be rebuilt on next check)
            cursor.execute('DELETE FROM listing_cache WHERE exchange = ?', (exchange,))
            
            conn.commit()
        
        print(f"✅ Updated {exchange} listings: {len(listings)} pairs")
    
    def get_exchange_stats(self) -> Dict[str, Dict]:
        """Get statistics for all exchanges"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exchange, last_updated, total_pairs, source
                FROM exchange_metadata
                ORDER BY exchange
            ''')
            
            stats = {}
            for row in cursor.fetchall():
                stats[row[0]] = {
                    'last_updated': row[1],
                    'total_pairs': row[2],
                    'source': row[3]
                }
            
            return stats
    
    def needs_update(self, exchange: str) -> bool:
        """Check if an exchange needs updating (older than REFRESH_DAYS)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT last_updated FROM exchange_metadata WHERE exchange = ?
            ''', (exchange,))
            
            result = cursor.fetchone()
            if not result:
                return True
            
            last_updated = datetime.fromisoformat(result[0])
            age = datetime.now() - last_updated
            return age.days >= self.REFRESH_DAYS
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn