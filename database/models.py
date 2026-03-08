"""Database models and schema"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

class Database:
    """Base database class"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database - to be overridden"""
        raise NotImplementedError
    
    def get_connection(self):
        """Get a database connection"""
        return sqlite3.connect(self.db_path)
    
    def execute(self, query: str, params: tuple = ()):
        """Execute a query and return cursor"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor

class HistoryDatabase(Database):
    """History database for scan results"""
    
    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create scan_history table per spec §8.1
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_date       TEXT NOT NULL,
                    coin_name       TEXT,
                    coin_symbol     TEXT NOT NULL,
                    gain_7d         REAL,
                    gain_30d        REAL,
                    uniformity_score REAL,
                    coinbase_volume TEXT,
                    kraken_volume   TEXT,
                    mexc_volume     TEXT,
                    cmc_url         TEXT
                )
            ''')
            
            # Create indexes per spec §8.1
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_scan_history_date 
                ON scan_history(scan_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_scan_history_symbol 
                ON scan_history(coin_symbol)
            ''')
            
            # Migrate existing data if needed: rename norm_slope to uniformity_score
            cursor.execute("PRAGMA table_info(scan_history)")
            columns = {row[1] for row in cursor.fetchall()}
            
            if 'norm_slope' in columns and 'uniformity_score' not in columns:
                # Create temporary table with new schema
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scan_history_new (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        scan_date       TEXT NOT NULL,
                        coin_name       TEXT,
                        coin_symbol     TEXT NOT NULL,
                        gain_7d         REAL,
                        gain_30d        REAL,
                        uniformity_score REAL,
                        coinbase_volume TEXT,
                        kraken_volume   TEXT,
                        mexc_volume     TEXT,
                        cmc_url         TEXT
                    )
                ''')
                
                # Copy data
                cursor.execute('''
                    INSERT INTO scan_history_new
                    (scan_date, coin_name, coin_symbol, gain_7d, gain_30d, uniformity_score,
                     coinbase_volume, kraken_volume, mexc_volume, cmc_url)
                    SELECT scan_date, coin_name, coin_symbol, gain_7d, gain_30d, norm_slope,
                           coinbase_volume, kraken_volume, mexc_volume, cmc_url
                    FROM scan_history
                ''')
                
                # Drop old and rename
                cursor.execute('DROP TABLE scan_history')
                cursor.execute('ALTER TABLE scan_history_new RENAME TO scan_history')
                
                # Recreate indexes
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scan_history_date 
                    ON scan_history(scan_date)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scan_history_symbol 
                    ON scan_history(coin_symbol)
                ''')
            
            conn.commit()
    
    def save_scan(self, coins: List[Dict[str, Any]]):
        """Save scan results"""
        now = datetime.now().isoformat()
        for coin in coins:
            self.execute('''
                INSERT INTO scan_history (
                    scan_date, coin_name, coin_symbol, gain_7d, gain_30d,
                    uniformity_score, coinbase_volume, kraken_volume, 
                    mexc_volume, cmc_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                now,
                coin['name'],
                coin['symbol'],
                coin['gains'].get('7d', 0),
                coin['gains'].get('30d', 0),
                coin.get('uniformity_score', 0),
                str(coin.get('exchange_volumes', {}).get('coinbase', 'N/A')),
                str(coin.get('exchange_volumes', {}).get('kraken', 'N/A')),
                str(coin.get('exchange_volumes', {}).get('mexc', 'N/A')),
                f"https://coinmarketcap.com/currencies/{coin['slug']}/"
            ))

class ActiveCoinsDatabase(Database):
    """Active coins tracking database"""
    
    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create active_coins table per spec §8.1
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_coins (
                    coin_symbol     TEXT NOT NULL PRIMARY KEY,
                    coin_name       TEXT NOT NULL,
                    gecko_id        TEXT,
                    entered_date    TEXT NOT NULL,
                    last_seen_date  TEXT NOT NULL,
                    last_scan_date  TEXT NOT NULL,
                    gain_7d         REAL,
                    gain_30d        REAL,
                    uniformity_score REAL,
                    coinbase_volume TEXT,
                    kraken_volume   TEXT,
                    mexc_volume     TEXT,
                    slug            TEXT,
                    cmc_url         TEXT
                )
            ''')
            
            # Migrate existing data if needed: rename norm_slope to uniformity_score
            # Check if old schema exists
            cursor.execute("PRAGMA table_info(active_coins)")
            columns = {row[1] for row in cursor.fetchall()}
            
            if 'norm_slope' in columns and 'uniformity_score' not in columns:
                # Need to migrate - create new table, copy data, drop old
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS active_coins_new (
                        coin_symbol     TEXT NOT NULL PRIMARY KEY,
                        coin_name       TEXT NOT NULL,
                        gecko_id        TEXT,
                        entered_date    TEXT NOT NULL,
                        last_seen_date  TEXT NOT NULL,
                        last_scan_date  TEXT NOT NULL,
                        gain_7d         REAL,
                        gain_30d        REAL,
                        uniformity_score REAL,
                        coinbase_volume TEXT,
                        kraken_volume   TEXT,
                        mexc_volume     TEXT,
                        slug            TEXT,
                        cmc_url         TEXT
                    )
                ''')
                
                # Copy data from old table
                cursor.execute('''
                    INSERT OR IGNORE INTO active_coins_new
                    (coin_symbol, coin_name, gecko_id, entered_date, last_seen_date, last_scan_date,
                     gain_7d, gain_30d, uniformity_score, coinbase_volume, kraken_volume, mexc_volume,
                     slug, cmc_url)
                    SELECT coin_symbol, coin_name, gecko_id, entered_date, last_seen_date, last_scan_date,
                           gain_7d, gain_30d, norm_slope, coinbase_volume, kraken_volume, mexc_volume,
                           slug, cmc_url
                    FROM active_coins
                ''')
                
                # Drop old and rename new
                cursor.execute('DROP TABLE active_coins')
                cursor.execute('ALTER TABLE active_coins_new RENAME TO active_coins')
            
            conn.commit()
    
    def get_active(self) -> Dict[str, Dict]:
        """Get all active coins - keyed by symbol only per spec §8.1"""
        cursor = self.execute('SELECT * FROM active_coins')
        active = {}
        for row in cursor.fetchall():
            # Key by symbol only (spec §8.1: PRIMARY KEY is coin_symbol alone)
            active[row[0]] = {
                'symbol': row[0],
                'name': row[1],
                'gecko_id': row[2],
                'entered_date': row[3],
                'last_seen_date': row[4],
                'last_scan_date': row[5],
                'gain_7d': row[6],
                'gain_30d': row[7],
                'uniformity_score': row[8],
                'coinbase_volume': row[9],
                'kraken_volume': row[10],
                'mexc_volume': row[11],
                'slug': row[12],
                'cmc_url': row[13]
            }
        return active
    
    def add_coin(self, coin: Dict[str, Any]):
        """Add a new active coin"""
        now = datetime.now().isoformat()
        today = datetime.now().strftime('%Y-%m-%d')
        
        gecko_id = coin.get('gecko_id') or coin.get('cg_id')
        
        self.execute('''
            INSERT OR REPLACE INTO active_coins 
            (coin_symbol, coin_name, gecko_id, entered_date, last_seen_date, last_scan_date,
             gain_7d, gain_30d, uniformity_score, coinbase_volume, kraken_volume, mexc_volume, slug, cmc_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            coin['symbol'], 
            coin['name'], 
            gecko_id,
            today, 
            today, 
            now,
            coin['gains'].get('7d', 0),
            coin['gains'].get('30d', 0),
            coin.get('uniformity_score', 0),
            str(coin.get('exchange_volumes', {}).get('coinbase', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('kraken', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('mexc', 'N/A')),
            coin.get('slug', coin['symbol'].lower()),
            f"https://coinmarketcap.com/currencies/{coin.get('slug', coin['symbol'].lower())}/"
        ))
    
    def remove_coin(self, symbol: str):
        """Remove a coin from active list - by symbol only per spec §8.1"""
        self.execute('DELETE FROM active_coins WHERE coin_symbol = ?', (symbol,))
    
    def update_coin(self, coin: Dict[str, Any]):
        """Update an existing active coin"""
        now = datetime.now().isoformat()
        
        gecko_id = coin.get('gecko_id') or coin.get('cg_id')
        
        self.execute('''
            UPDATE active_coins 
            SET last_seen_date = ?, last_scan_date = ?,
                gecko_id = ?,
                gain_7d = ?, gain_30d = ?, uniformity_score = ?,
                coinbase_volume = ?, kraken_volume = ?, mexc_volume = ?,
                slug = ?, cmc_url = ?
            WHERE coin_symbol = ?
        ''', (
            now, now,
            gecko_id,
            coin['gains'].get('7d', 0),
            coin['gains'].get('30d', 0),
            coin.get('uniformity_score', 0),
            str(coin.get('exchange_volumes', {}).get('coinbase', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('kraken', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('mexc', 'N/A')),
            coin.get('slug', coin['symbol'].lower()),
            f"https://coinmarketcap.com/currencies/{coin.get('slug', coin['symbol'].lower())}/",
            coin['symbol']
        ))
    
    def get_entered_exited(self, current_coins: List[Dict[str, Any]]) -> tuple:
        """
        Compare current coins with active coins to find entries and exits.
        Returns (entered, exited) tuples.
        Keyed by symbol only per spec §8.1.
        """
        active = self.get_active()
        
        # Create set of current coin symbols (not name_symbol pairs)
        current_symbols = {c['symbol'] for c in current_coins}
        current_dict = {c['symbol']: c for c in current_coins}
        
        # Find entered (in current but not in active)
        entered = []
        for symbol in current_symbols - set(active.keys()):
            coin = current_dict[symbol]
            entered.append(coin)
            self.add_coin(coin)
        
        # Find exited (in active but not in current)
        exited = []
        for symbol in set(active.keys()) - current_symbols:
            coin_info = active[symbol]
            exited.append({
                'symbol': coin_info['symbol'],
                'name': coin_info['name'],
                'slug': coin_info['slug']
            })
            self.remove_coin(symbol)
        
        # Update remaining active coins
        for symbol in current_symbols & set(active.keys()):
            self.update_coin(current_dict[symbol])
        
        return entered, exited