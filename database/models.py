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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_date TEXT,
                    coin_name TEXT,
                    coin_symbol TEXT,
                    gain_7d REAL,
                    gain_30d REAL,
                    norm_slope REAL,
                    coinbase_volume TEXT,
                    kraken_volume TEXT,
                    mexc_volume TEXT,
                    cmc_url TEXT
                )
            ''')
    
    def save_scan(self, coins: List[Dict[str, Any]]):
        """Save scan results"""
        now = datetime.now().isoformat()
        for coin in coins:
            self.execute('''
                INSERT INTO scan_history (
                    scan_date, coin_name, coin_symbol, gain_7d, gain_30d,
                    norm_slope, coinbase_volume, kraken_volume, 
                    mexc_volume, cmc_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                now,
                coin['name'],
                coin['symbol'],
                coin['gains'].get('7d', 0),
                coin['gains'].get('30d', 0),
                coin.get('norm_slope', 0),
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_coins (
                    coin_symbol TEXT,
                    coin_name TEXT,
                    gecko_id TEXT,
                    coinlore_id TEXT,
                    entered_date TEXT,
                    last_seen_date TEXT,
                    last_scan_date TEXT,
                    gain_7d REAL,
                    gain_30d REAL,
                    norm_slope REAL,
                    coinbase_volume TEXT,
                    kraken_volume TEXT,
                    mexc_volume TEXT,
                    slug TEXT,
                    cmc_url TEXT,
                    PRIMARY KEY (coin_symbol, coin_name)
                )
            ''')
    
    def get_active(self) -> Dict[str, Dict]:
        """Get all active coins"""
        cursor = self.execute('SELECT * FROM active_coins')
        active = {}
        for row in cursor.fetchall():
            key = f"{row[1]}_{row[0]}"  # name_symbol
            active[key] = {
                'symbol': row[0],
                'name': row[1],
                'gecko_id': row[2],
                'coinlore_id': row[3],
                'entered_date': row[4],
                'last_seen_date': row[5],
                'last_scan_date': row[6],
                'gain_7d': row[7],
                'gain_30d': row[8],
                'norm_slope': row[9],
                'coinbase_volume': row[10],
                'kraken_volume': row[11],
                'mexc_volume': row[12],
                'slug': row[13],
                'cmc_url': row[14]
            }
        return active
    
    def add_coin(self, coin: Dict[str, Any]):
        """Add a new active coin"""
        now = datetime.now().isoformat()
        today = datetime.now().strftime('%Y-%m-%d')
        
        gecko_id = coin.get('gecko_id') or coin.get('cg_id')
        coinlore_id = coin.get('coinlore_id')
        
        print(f"DEBUG - Adding coin to active_db: {coin['symbol']}")
        print(f"DEBUG - Gecko ID: {gecko_id}")
        print(f"DEBUG - CoinLore ID: {coinlore_id}")
        print(f"DEBUG - Slug: {coin.get('slug', 'MISSING')}")
        
        self.execute('''
            INSERT OR REPLACE INTO active_coins 
            (coin_symbol, coin_name, gecko_id, coinlore_id, entered_date, last_seen_date, last_scan_date,
             gain_7d, gain_30d, norm_slope, coinbase_volume, kraken_volume, mexc_volume, slug, cmc_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            coin['symbol'], 
            coin['name'], 
            gecko_id,
            coinlore_id,
            today, 
            now, 
            now,
            coin['gains'].get('7d', 0),
            coin['gains'].get('30d', 0),
            coin.get('norm_slope', 0),
            str(coin.get('exchange_volumes', {}).get('coinbase', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('kraken', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('mexc', 'N/A')),
            coin.get('slug', coin['symbol'].lower()),
            f"https://coinmarketcap.com/currencies/{coin.get('slug', coin['symbol'].lower())}/"
        ))
    
    def remove_coin(self, symbol: str, name: str):
        """Remove a coin from active list"""
        self.execute('DELETE FROM active_coins WHERE coin_symbol = ? AND coin_name = ?', (symbol, name))
    
    def update_coin(self, coin: Dict[str, Any]):
        """Update an existing active coin"""
        now = datetime.now().isoformat()
        
        gecko_id = coin.get('gecko_id') or coin.get('cg_id')
        coinlore_id = coin.get('coinlore_id')
        
        self.execute('''
            UPDATE active_coins 
            SET last_seen_date = ?, last_scan_date = ?,
                gecko_id = ?, coinlore_id = ?,
                gain_7d = ?, gain_30d = ?, norm_slope = ?,
                coinbase_volume = ?, kraken_volume = ?, mexc_volume = ?,
                slug = ?, cmc_url = ?
            WHERE coin_symbol = ? AND coin_name = ?
        ''', (
            now, now,
            gecko_id,
            coinlore_id,
            coin['gains'].get('7d', 0),
            coin['gains'].get('30d', 0),
            coin.get('norm_slope', 0),
            str(coin.get('exchange_volumes', {}).get('coinbase', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('kraken', 'N/A')),
            str(coin.get('exchange_volumes', {}).get('mexc', 'N/A')),
            coin.get('slug', coin['symbol'].lower()),
            f"https://coinmarketcap.com/currencies/{coin.get('slug', coin['symbol'].lower())}/",
            coin['symbol'], 
            coin['name']
        ))
    
    def get_entered_exited(self, current_coins: List[Dict[str, Any]]) -> tuple:
        """
        Compare current coins with active coins to find entries and exits.
        Returns (entered, exited) tuples.
        """
        active = self.get_active()
        
        # Create set of current coin keys
        current_keys = {f"{c['name']}_{c['symbol']}" for c in current_coins}
        current_dict = {f"{c['name']}_{c['symbol']}": c for c in current_coins}
        
        # Find entered (in current but not in active)
        entered = []
        for key in current_keys - set(active.keys()):
            coin = current_dict[key]
            entered.append(coin)
            self.add_coin(coin)
        
        # Find exited (in active but not in current)
        exited = []
        for key in set(active.keys()) - current_keys:
            coin_info = active[key]
            exited.append({
                'symbol': coin_info['symbol'],
                'name': coin_info['name'],
                'slug': coin_info['slug']
            })
            self.remove_coin(coin_info['symbol'], coin_info['name'])
        
        # Update remaining active coins
        for key in current_keys & set(active.keys()):
            self.update_coin(current_dict[key])
        
        return entered, exited