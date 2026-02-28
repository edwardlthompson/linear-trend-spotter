"""
CoinGecko ID Mapper - Maintains a local mapping of symbols to CoinGecko API IDs
Uses the /coins/list endpoint to build and cache the mapping
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import threading
import logging
import requests

class CoinGeckoMapper:
    """
    Maintains a local database of CoinGecko IDs mapped to symbols
    Refreshes weekly or on demand
    """
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.logger = logging.getLogger('CoinGeckoMapper')
        self._local = threading.local()
        self._init_db()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Linear-Trend-Spotter/1.0'
        })
        self.last_request = 0
    
    def _get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(str(self.db_path), timeout=10)
            self._local.conn.execute('PRAGMA journal_mode=WAL')
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _execute(self, query: str, params: tuple = ()):
        """Execute a database query"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor
    
    def _init_db(self):
        """Initialize database tables"""
        # Main mapping table
        self._execute('''
            CREATE TABLE IF NOT EXISTS coin_mappings (
                symbol TEXT,
                coin_id TEXT,
                name TEXT,
                last_updated TEXT,
                PRIMARY KEY (symbol, coin_id)
            )
        ''')
        
        # Create index for fast lookups
        self._execute('''
            CREATE INDEX IF NOT EXISTS idx_coin_mappings_symbol ON coin_mappings(symbol)
        ''')
        
        # Cache metadata
        self._execute('''
            CREATE TABLE IF NOT EXISTS mapping_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                last_updated TEXT
            )
        ''')
    
    def _rate_limit(self):
        """Simple rate limiting"""
        now = time.time()
        elapsed = now - self.last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request = time.time()
    
    def fetch_coingecko_list(self) -> Optional[List[Dict]]:
        """
        Fetch the complete coin list from CoinGecko
        Returns list of dicts with id, symbol, name
        """
        try:
            self._rate_limit()
            url = f"{self.BASE_URL}/coins/list"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"✅ Fetched {len(data)} coins from CoinGecko")
                return data
            else:
                self.logger.error(f"❌ Failed to fetch coin list: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error fetching coin list: {e}")
            return None
    
    def update_mappings(self) -> int:
        """
        Update the local mapping database with fresh data from CoinGecko
        Returns number of mappings added
        """
        self.logger.info("🔄 Updating CoinGecko mappings...")
        
        coins = self.fetch_coingecko_list()
        if not coins:
            return 0
        
        now = datetime.now().isoformat()
        added = 0
        
        # Prepare data for bulk insert
        data = []
        for coin in coins:
            symbol = coin.get('symbol', '').upper()
            coin_id = coin.get('id', '')
            name = coin.get('name', '')
            if symbol and coin_id:
                data.append((symbol, coin_id, name, now))
                added += 1
        
        # Bulk insert
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Clear old data and insert new
        cursor.execute('DELETE FROM coin_mappings')
        cursor.executemany('''
            INSERT INTO coin_mappings (symbol, coin_id, name, last_updated)
            VALUES (?, ?, ?, ?)
        ''', data)
        
        # Update metadata
        cursor.execute('''
            INSERT OR REPLACE INTO mapping_metadata (key, value, last_updated)
            VALUES (?, ?, ?)
        ''', ('last_update', now, now))
        
        cursor.execute('''
            INSERT OR REPLACE INTO mapping_metadata (key, value, last_updated)
            VALUES (?, ?, ?)
        ''', ('total_mappings', str(added), now))
        
        conn.commit()
        
        self.logger.info(f"✅ Updated {added} CoinGecko mappings")
        return added
    
    def get_coin_id(self, symbol: str) -> Optional[str]:
        """
        Get CoinGecko ID for a symbol
        Returns the most likely match (by market cap ranking)
        """
        if not symbol:
            return None
        
        cursor = self._execute('''
            SELECT coin_id FROM coin_mappings 
            WHERE symbol = ?
            ORDER BY rowid  -- This approximates market cap ranking
            LIMIT 1
        ''', (symbol.upper(),))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    
    def get_coin_ids_batch(self, symbols: List[str]) -> Dict[str, str]:
        """
        Get CoinGecko IDs for multiple symbols in one query
        """
        if not symbols:
            return {}
        
        symbols_upper = [s.upper() for s in symbols]
        placeholders = ','.join(['?' for _ in symbols_upper])
        
        cursor = self._execute(f'''
            SELECT symbol, coin_id FROM coin_mappings 
            WHERE symbol IN ({placeholders})
            GROUP BY symbol  -- Take first occurrence (highest ranked)
        ''', symbols_upper)
        
        results = {}
        for row in cursor.fetchall():
            results[row[0]] = row[1]
        
        return results
    
    def get_all_mappings(self) -> Dict[str, str]:
        """Get all symbol to ID mappings"""
        cursor = self._execute('SELECT symbol, coin_id FROM coin_mappings')
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def get_stats(self) -> Dict[str, any]:
        """Get mapping statistics"""
        cursor = self._execute('SELECT COUNT(*) FROM coin_mappings')
        total = cursor.fetchone()[0]
        
        cursor = self._execute('SELECT value FROM mapping_metadata WHERE key = ?', ('last_update',))
        last_update = cursor.fetchone()
        
        return {
            'total_mappings': total,
            'last_update': last_update[0] if last_update else 'Never'
        }
    
    def debug_check_symbol(self, symbol: str):
        """Debug method to check all mappings for a symbol"""
        cursor = self._execute('''
            SELECT coin_id, name FROM coin_mappings 
            WHERE symbol = ?
        ''', (symbol.upper(),))
        
        results = cursor.fetchall()
        if results:
            print(f"\n📊 Mappings for {symbol}:")
            for row in results:
                print(f"   ID: {row[0]}, Name: {row[1]}")
        else:
            print(f"\n❌ No mappings found for {symbol}")
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn