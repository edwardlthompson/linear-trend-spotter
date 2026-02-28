"""
Cache management for CoinLore data
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import threading

class CoinLoreCache:
    """
    Cache for CoinLore API data
    """

    COIN_LIST_CACHE_DURATION = 24 * 60 * 60  # 24 hours
    PRICE_CACHE_DURATION = 6 * 60 * 60       # 6 hours

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_cache()

    def _get_connection(self):
        """Get a thread-local database connection"""
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

    def _init_cache(self):
        """Initialize cache tables with correct schema"""
        # Coin list table
        self._execute('''
            CREATE TABLE IF NOT EXISTS coin_list (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                rank INTEGER,
                last_updated TEXT
            )
        ''')

        self._execute('''
            CREATE INDEX IF NOT EXISTS idx_coin_list_symbol ON coin_list(symbol)
        ''')

        # Price cache table
        self._execute('''
            CREATE TABLE IF NOT EXISTS price_cache (
                coin_id TEXT PRIMARY KEY,
                prices TEXT,
                uniformity_score REAL DEFAULT 0,
                gains_30d REAL DEFAULT 0,
                gains_60d REAL DEFAULT 0,
                gains_90d REAL DEFAULT 0,
                cache_date TEXT
            )
        ''')

    def update_coin_list(self, coins: List[Dict]) -> int:
        """Bulk update coin list"""
        try:
            now = datetime.now().isoformat()
            data = [(c['coin_id'], c['symbol'].lower(), c['name'], c['rank'], now) for c in coins]

            self._execute('DELETE FROM coin_list')

            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO coin_list (id, symbol, name, rank, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', data)
            conn.commit()

            return len(coins)

        except Exception as e:
            print(f"⚠️ Error updating coin list: {e}")
            return 0

    def get_coin_ids_batch(self, symbols: List[str]) -> Dict[str, str]:
        """
        Get coin IDs for multiple symbols
        Converts all input symbols to lowercase for case-insensitive lookup
        """
        if not symbols:
            return {}

        try:
            symbols_lower = [s.lower() for s in symbols]
            placeholders = ','.join(['?' for _ in symbols_lower])

            cursor = self._execute(f'''
                SELECT symbol, id FROM coin_list
                WHERE symbol IN ({placeholders})
            ''', symbols_lower)

            results = {}
            for row in cursor.fetchall():
                results[row[0].upper()] = row[1]

            return results

        except Exception as e:
            print(f"⚠️ Error getting coin IDs: {e}")
            return {}

    def get_coin_list_stats(self) -> Dict[str, Any]:
        """Get statistics about the coin list"""
        try:
            cursor = self._execute('SELECT COUNT(*) FROM coin_list')
            total = cursor.fetchone()[0]

            cursor = self._execute('SELECT MAX(last_updated) FROM coin_list')
            last_update = cursor.fetchone()[0]

            return {
                'total_coins': total,
                'last_update': last_update or 'Never',
            }
        except Exception as e:
            return {'total_coins': 0, 'last_update': 'Unknown'}

    def debug_coin_list(self) -> int:
        """Debug coin list contents"""
        try:
            cursor = self._execute('SELECT COUNT(*) FROM coin_list')
            total = cursor.fetchone()[0]
            print(f"\n📊 Coin List Statistics:")
            print(f"   Total coins: {total}")

            if total > 0:
                cursor = self._execute('SELECT id, symbol, rank FROM coin_list LIMIT 10')
                print("   Sample entries:")
                for row in cursor.fetchall():
                    print(f"      ID: {row[0]}, Symbol: {row[1]}, Rank: {row[2]}")

            return total
        except Exception as e:
            print(f"Error debugging: {e}")
            return 0

    def get_price_data(self, coin_id: str) -> Tuple[bool, Optional[Dict]]:
        """Get cached price data"""
        try:
            six_hours_ago = (datetime.now() - timedelta(seconds=self.PRICE_CACHE_DURATION)).isoformat()

            cursor = self._execute('''
                SELECT prices, uniformity_score, gains_30d, gains_60d, gains_90d
                FROM price_cache
                WHERE coin_id = ? AND cache_date > ?
            ''', (coin_id, six_hours_ago))

            result = cursor.fetchone()
            if result:
                return True, {
                    'prices': json.loads(result[0]),
                    'uniformity_score': result[1],
                    'gains_30d': result[2],
                    'gains_60d': result[3],
                    'gains_90d': result[4],
                }

            return False, None
        except Exception as e:
            return False, None

    def cache_price_data(self, coin_id: str, prices: list, uniformity_score: float,
                        gains_30d: float, gains_60d: float, gains_90d: float):
        """Cache price data and metrics"""
        try:
            now = datetime.now().isoformat()
            self._execute('''
                INSERT OR REPLACE INTO price_cache
                (coin_id, prices, uniformity_score, gains_30d, gains_60d, gains_90d, cache_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (coin_id, json.dumps(prices), uniformity_score, gains_30d, gains_60d, gains_90d, now))
        except Exception as e:
            pass

    def print_cache_summary(self):
        """Print a comprehensive cache summary"""
        coin_stats = self.get_coin_list_stats()

        # Get price cache stats
        try:
            cursor = self._execute('SELECT COUNT(*) FROM price_cache')
            price_count = cursor.fetchone()[0]

            # Get oldest and newest cache entries
            cursor = self._execute('SELECT MIN(cache_date), MAX(cache_date) FROM price_cache')
            date_range = cursor.fetchone()
            oldest = date_range[0][:16] if date_range[0] else 'Never'
            newest = date_range[1][:16] if date_range[1] else 'Never'

            # Get average uniformity score (optional)
            cursor = self._execute('SELECT AVG(uniformity_score) FROM price_cache WHERE uniformity_score > 0')
            avg_score = cursor.fetchone()[0]
            avg_score = round(avg_score, 1) if avg_score else 0

        except Exception as e:
            price_count = 0
            oldest = 'Never'
            newest = 'Never'
            avg_score = 0
            print(f"Debug - Error getting price cache stats: {e}")

        print("\n" + "=" * 50)
        print("📊 CACHE SUMMARY")
        print("=" * 50)

        print("\n💰 Coin List:")
        print(f"   Total coins: {coin_stats['total_coins']}")
        print(f"   Last updated: {coin_stats['last_update'][:16] if coin_stats['last_update'] != 'Never' else 'Never'}")

        print(f"\n📈 Price Cache:")
        print(f"   Cached coins: {price_count}")
        if price_count > 0:
            print(f"   Oldest: {oldest}")
            print(f"   Newest: {newest}")
            print(f"   Avg uniformity: {avg_score}")

        print("=" * 50)

    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn