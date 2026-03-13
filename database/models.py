"""Database models and schema"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any


def _build_source_url(coin: Dict[str, Any]) -> str:
    source_url = str(coin.get('source_url') or coin.get('cmc_url') or '').strip()
    if source_url:
        return source_url

    gecko_id = str(coin.get('gecko_id') or coin.get('cg_id') or '').strip()
    if gecko_id:
        return f"https://www.coingecko.com/en/coins/{gecko_id}"

    slug = str(coin.get('slug') or '').strip().lower()
    if slug:
        return f"https://coinmarketcap.com/currencies/{slug}/"

    symbol = str(coin.get('symbol') or coin.get('coin_symbol') or '').strip()
    if symbol:
        return f"https://www.coingecko.com/en/search?query={symbol}"

    return ''

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
                _build_source_url(coin)
            ))

    def get_latest_rank_map(self) -> Dict[str, int]:
        """Return symbol->rank map for the most recent saved scan."""
        cursor = self.execute('SELECT MAX(scan_date) FROM scan_history')
        row = cursor.fetchone()
        latest_scan_date = row[0] if row else None
        if not latest_scan_date:
            return {}

        cursor = self.execute('''
            SELECT coin_symbol
            FROM scan_history
            WHERE scan_date = ?
            ORDER BY uniformity_score DESC, gain_30d DESC, coin_symbol ASC
        ''', (latest_scan_date,))

        return {
            str(symbol_row[0]).upper(): index
            for index, symbol_row in enumerate(cursor.fetchall(), start=1)
            if symbol_row and symbol_row[0]
        }

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
                    cmc_url         TEXT,
                    entry_price     REAL,
                    peak_price      REAL,
                    trough_price    REAL,
                    last_price      REAL,
                    lifecycle_updated_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cooldown_exits (
                    coin_symbol         TEXT NOT NULL PRIMARY KEY,
                    last_exit_ts        TEXT NOT NULL,
                    cooldown_until_ts   TEXT NOT NULL,
                    exit_reason         TEXT
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

            cursor.execute("PRAGMA table_info(active_coins)")
            active_columns = {row[1] for row in cursor.fetchall()}
            if 'entry_price' not in active_columns:
                cursor.execute('ALTER TABLE active_coins ADD COLUMN entry_price REAL')
            if 'peak_price' not in active_columns:
                cursor.execute('ALTER TABLE active_coins ADD COLUMN peak_price REAL')
            if 'trough_price' not in active_columns:
                cursor.execute('ALTER TABLE active_coins ADD COLUMN trough_price REAL')
            if 'last_price' not in active_columns:
                cursor.execute('ALTER TABLE active_coins ADD COLUMN last_price REAL')
            if 'lifecycle_updated_at' not in active_columns:
                cursor.execute('ALTER TABLE active_coins ADD COLUMN lifecycle_updated_at TEXT')
            
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
                'cmc_url': row[13],
                'source_url': row[13],
                'entry_price': row[14] if len(row) > 14 else None,
                'peak_price': row[15] if len(row) > 15 else None,
                'trough_price': row[16] if len(row) > 16 else None,
                'last_price': row[17] if len(row) > 17 else None,
                'lifecycle_updated_at': row[18] if len(row) > 18 else None,
            }
        return active
    
    def add_coin(self, coin: Dict[str, Any]):
        """Add a new active coin"""
        now = datetime.now().isoformat()
        today = datetime.now().strftime('%Y-%m-%d')
        
        gecko_id = coin.get('gecko_id') or coin.get('cg_id')
        current_price = float(coin.get('current_price', 0) or 0)
        lifecycle_price = current_price if current_price > 0 else None
        
        self.execute('''
            INSERT OR REPLACE INTO active_coins 
            (coin_symbol, coin_name, gecko_id, entered_date, last_seen_date, last_scan_date,
             gain_7d, gain_30d, uniformity_score, coinbase_volume, kraken_volume, mexc_volume, slug, cmc_url,
             entry_price, peak_price, trough_price, last_price, lifecycle_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            _build_source_url(coin),
            lifecycle_price,
            lifecycle_price,
            lifecycle_price,
            lifecycle_price,
            now,
        ))
    
    def remove_coin(self, symbol: str):
        """Remove a coin from active list - by symbol only per spec §8.1"""
        self.execute('DELETE FROM active_coins WHERE coin_symbol = ?', (symbol,))
    
    def update_coin(self, coin: Dict[str, Any]):
        """Update an existing active coin"""
        now = datetime.now().isoformat()
        
        gecko_id = coin.get('gecko_id') or coin.get('cg_id')
        current_price = float(coin.get('current_price', 0) or 0)
        
        self.execute('''
            UPDATE active_coins 
            SET last_seen_date = ?, last_scan_date = ?,
                gecko_id = ?,
                gain_7d = ?, gain_30d = ?, uniformity_score = ?,
                coinbase_volume = ?, kraken_volume = ?, mexc_volume = ?,
                slug = ?, cmc_url = ?
                , last_price = CASE WHEN ? > 0 THEN ? ELSE last_price END
                , peak_price = CASE
                    WHEN ? > 0 AND (peak_price IS NULL OR peak_price <= 0 OR ? > peak_price) THEN ?
                    ELSE peak_price
                END
                , trough_price = CASE
                    WHEN ? > 0 AND (trough_price IS NULL OR trough_price <= 0 OR ? < trough_price) THEN ?
                    ELSE trough_price
                END
                , lifecycle_updated_at = ?
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
            _build_source_url(coin),
            current_price,
            current_price,
            current_price,
            current_price,
            current_price,
            current_price,
            current_price,
            current_price,
            now,
            coin['symbol']
        ))

    def register_exit(self, symbol: str, reason: str = '', cooldown_hours: int = 0):
        """Persist last exit and cooldown state for a symbol."""
        now = datetime.now()
        cooldown_until = now + timedelta(hours=max(0, int(cooldown_hours)))
        self.execute('''
            INSERT OR REPLACE INTO cooldown_exits (coin_symbol, last_exit_ts, cooldown_until_ts, exit_reason)
            VALUES (?, ?, ?, ?)
        ''', (
            symbol,
            now.isoformat(),
            cooldown_until.isoformat(),
            str(reason or '').strip(),
        ))

    def get_recent_exits(self, days: int = 7) -> list[dict[str, Any]]:
        """Return exits within a time window for digest/reporting."""
        cutoff = datetime.now() - timedelta(days=max(1, int(days)))
        cursor = self.execute('''
            SELECT coin_symbol, last_exit_ts, exit_reason
            FROM cooldown_exits
            WHERE last_exit_ts >= ?
            ORDER BY last_exit_ts DESC
        ''', (cutoff.isoformat(),))
        return [
            {
                'symbol': row[0],
                'last_exit_ts': row[1],
                'exit_reason': row[2] or '',
            }
            for row in cursor.fetchall()
        ]

    def _get_cooldown_until(self, symbol: str) -> Optional[datetime]:
        cursor = self.execute(
            'SELECT cooldown_until_ts FROM cooldown_exits WHERE coin_symbol = ?',
            (symbol,),
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return None
        try:
            return datetime.fromisoformat(str(row[0]))
        except Exception:
            return None
    
    def get_entered_exited(self, current_coins: List[Dict[str, Any]], cooldown_hours: int = 0) -> tuple:
        """
        Compare current coins with active coins to find entries and exits.
        Returns (entered, exited, blocked_by_cooldown) tuples.
        Keyed by symbol only per spec §8.1.
        """
        active = self.get_active()
        now = datetime.now()
        
        # Create set of current coin symbols (not name_symbol pairs)
        current_symbols = {c['symbol'] for c in current_coins}
        current_dict = {c['symbol']: c for c in current_coins}
        
        # Find entered (in current but not in active)
        entered = []
        blocked_by_cooldown = []
        for symbol in current_symbols - set(active.keys()):
            cooldown_until = self._get_cooldown_until(symbol)
            if cooldown_until and cooldown_until > now:
                blocked_by_cooldown.append({
                    'symbol': symbol,
                    'cooldown_until': cooldown_until.isoformat(),
                })
                continue
            coin = current_dict[symbol]
            entered.append(coin)
            self.add_coin(coin)
        
        # Find exited (in active but not in current)
        exited = []
        for symbol in set(active.keys()) - current_symbols:
            coin_info = active[symbol]
            entry_price = float(coin_info.get('entry_price') or 0)
            peak_price = float(coin_info.get('peak_price') or 0)
            trough_price = float(coin_info.get('trough_price') or 0)
            last_price = float(coin_info.get('last_price') or 0)

            lifecycle = {}
            if entry_price > 0 and last_price > 0:
                lifecycle['lifecycle_pnl_pct'] = ((last_price - entry_price) / entry_price) * 100.0
            if entry_price > 0 and peak_price > 0:
                lifecycle['max_runup_pct'] = ((peak_price - entry_price) / entry_price) * 100.0
            if entry_price > 0 and trough_price > 0:
                lifecycle['max_drawdown_pct'] = ((trough_price - entry_price) / entry_price) * 100.0
            entered_date_raw = str(coin_info.get('entered_date') or '')
            if entered_date_raw:
                try:
                    entered_dt = datetime.fromisoformat(entered_date_raw)
                except Exception:
                    try:
                        entered_dt = datetime.strptime(entered_date_raw, '%Y-%m-%d')
                    except Exception:
                        entered_dt = None
                if entered_dt:
                    lifecycle['held_days'] = max(0, (now - entered_dt).days)

            exited.append({
                'symbol': coin_info['symbol'],
                'name': coin_info['name'],
                'slug': coin_info['slug'],
                **lifecycle,
            })
            self.remove_coin(symbol)
            self.register_exit(symbol, reason='No longer qualified', cooldown_hours=cooldown_hours)
        
        # Update remaining active coins
        for symbol in current_symbols & set(active.keys()):
            self.update_coin(current_dict[symbol])
        
        return entered, exited, blocked_by_cooldown