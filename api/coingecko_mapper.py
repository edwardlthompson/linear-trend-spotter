"""
CoinGecko ID Mapper - Maintains a local mapping of symbols to CoinGecko API IDs
Uses the /coins/list endpoint to build and cache the mapping
"""

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, List
import threading
import logging
import requests

from utils.coingecko_usage import record_coingecko_http


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
        """Initialize database tables per spec §8.3"""
        # Main mapping table - symbol_mapping per spec §8.3
        self._execute('''
            CREATE TABLE IF NOT EXISTS symbol_mapping (
                symbol          TEXT NOT NULL,
                name            TEXT,
                coingecko_id    TEXT NOT NULL,
                confidence      INTEGER,
                source          TEXT,
                last_updated    TEXT,
                PRIMARY KEY (symbol, coingecko_id)
            )
        ''')
        
        # Create index per spec §8.3
        self._execute('''
            CREATE INDEX IF NOT EXISTS idx_mapping_symbol ON symbol_mapping(symbol)
        ''')
        
        # Cache metadata - mapping_metadata per spec §8.3
        self._execute('''
            CREATE TABLE IF NOT EXISTS mapping_metadata (
                key     TEXT PRIMARY KEY,
                value   TEXT,
                last_updated TEXT
            )
        ''')

        # Backward compatibility: older DBs may not have last_updated
        try:
            self._execute('ALTER TABLE mapping_metadata ADD COLUMN last_updated TEXT')
        except sqlite3.OperationalError:
            pass
    
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
                record_coingecko_http(response.url)
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
        cursor.execute('DELETE FROM symbol_mapping')
        cursor.executemany('''
            INSERT INTO symbol_mapping (symbol, coingecko_id, name, last_updated)
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
            SELECT coingecko_id FROM symbol_mapping 
            WHERE symbol = ?
            ORDER BY rowid  -- This approximates market cap ranking
            LIMIT 1
        ''', (symbol.upper(),))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        return None

    def get_coin_id_with_name_hint(self, symbol: str, name: Optional[str]) -> Optional[str]:
        """
        Resolve CoinGecko id for a ticker, preferring a row whose ``name`` matches (for duplicate symbols).
        Used when ``TOP_COINS_PROVIDER`` is CMC: listings carry symbol + name but not CoinGecko id.
        """
        if not symbol:
            return None
        sym = symbol.upper()
        nm = str(name or "").strip()
        if nm:
            cursor = self._execute(
                """
                SELECT coingecko_id FROM symbol_mapping
                WHERE symbol = ? AND lower(trim(coalesce(name, ''))) = lower(trim(?))
                LIMIT 1
                """,
                (sym, nm),
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        return self.get_coin_id(sym)

    def get_coin_ids_batch(self, symbols: List[str]) -> Dict[str, str]:
        """
        Get CoinGecko IDs for multiple symbols in one query
        """
        if not symbols:
            return {}
        
        symbols_upper = [s.upper() for s in symbols]
        placeholders = ','.join(['?' for _ in symbols_upper])
        
        cursor = self._execute(f'''
            SELECT symbol, coingecko_id FROM symbol_mapping 
            WHERE symbol IN ({placeholders})
            GROUP BY symbol  -- Take first occurrence (highest ranked)
        ''', symbols_upper)
        
        results = {}
        for row in cursor.fetchall():
            results[row[0]] = row[1]
        
        return results
    
    def get_all_mappings(self) -> Dict[str, str]:
        """Get all symbol to ID mappings"""
        cursor = self._execute('SELECT symbol, coingecko_id FROM symbol_mapping')
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def get_stats(self) -> Dict[str, any]:
        """Get mapping statistics"""
        cursor = self._execute('SELECT COUNT(*) FROM symbol_mapping')
        total = cursor.fetchone()[0]
        
        cursor = self._execute('SELECT value FROM mapping_metadata WHERE key = ?', ('last_update',))
        last_update = cursor.fetchone()
        
        return {
            'total_mappings': total,
            'last_update': last_update[0] if last_update else 'Never'
        }

    def should_refresh_list(self, max_age_days: int) -> bool:
        """True if mapping table is empty or last /coins/list refresh is older than max_age_days."""
        stats = self.get_stats()
        if int(stats.get('total_mappings') or 0) == 0:
            return True
        raw = stats.get('last_update') or 'Never'
        if raw in ('Never', '', None):
            return True
        try:
            text = str(raw).strip().replace('Z', '+00:00')
            last = datetime.fromisoformat(text)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            else:
                last = last.astimezone(timezone.utc)
            age_limit = datetime.now(timezone.utc) - timedelta(days=max(1, int(max_age_days)))
            return last < age_limit
        except (TypeError, ValueError, OSError):
            return True

    def debug_check_symbol(self, symbol: str):
        """Debug method to check all mappings for a symbol"""
        cursor = self._execute('''
            SELECT coingecko_id, name FROM symbol_mapping 
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