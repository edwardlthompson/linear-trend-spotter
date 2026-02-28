#!/usr/bin/env python3
"""
Migration script to update both active_coins and scan_history tables
Adds gain_7d and gain_30d columns
"""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

def migrate_active_coins(cursor):
    """Update active_coins table"""
    print("\n🔄 Migrating active_coins table...")
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(active_coins)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"   Current columns: {columns}")
    
    # If old total_gain exists, we need to recreate the table
    if 'total_gain' in columns:
        print("   Recreating table with new schema...")
        
        # Create new table with updated schema
        cursor.execute('''
            CREATE TABLE active_coins_new (
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
        
        # Copy data from old table
        cursor.execute('''
            INSERT INTO active_coins_new 
            SELECT 
                coin_symbol, coin_name, gecko_id, coinlore_id, entered_date, last_seen_date, last_scan_date,
                0 as gain_7d,
                total_gain as gain_30d,
                norm_slope,
                coinbase_volume, kraken_volume, mexc_volume, slug, cmc_url
            FROM active_coins
        ''')
        
        # Drop old table and rename new one
        cursor.execute('DROP TABLE active_coins')
        cursor.execute('ALTER TABLE active_coins_new RENAME TO active_coins')
        print("   ✅ active_coins table recreated")
    else:
        # Add columns if they don't exist
        if 'gain_7d' not in columns:
            cursor.execute("ALTER TABLE active_coins ADD COLUMN gain_7d REAL DEFAULT 0")
            print("   ✅ Added gain_7d to active_coins")
        
        if 'gain_30d' not in columns:
            cursor.execute("ALTER TABLE active_coins ADD COLUMN gain_30d REAL DEFAULT 0")
            print("   ✅ Added gain_30d to active_coins")

def migrate_scan_history(cursor):
    """Update scan_history table"""
    print("\n🔄 Migrating scan_history table...")
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(scan_history)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"   Current columns: {columns}")
    
    # If old total_gain exists, we need to recreate the table
    if 'total_gain' in columns:
        print("   Recreating table with new schema...")
        
        # Create new table with updated schema
        cursor.execute('''
            CREATE TABLE scan_history_new (
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
        
        # Copy data from old table
        cursor.execute('''
            INSERT INTO scan_history_new (
                id, scan_date, coin_name, coin_symbol, gain_7d, gain_30d, norm_slope,
                coinbase_volume, kraken_volume, mexc_volume, cmc_url
            )
            SELECT 
                id, scan_date, coin_name, coin_symbol,
                0 as gain_7d,
                total_gain as gain_30d,
                norm_slope,
                coinbase_volume, kraken_volume, mexc_volume, cmc_url
            FROM scan_history
        ''')
        
        # Drop old table and rename new one
        cursor.execute('DROP TABLE scan_history')
        cursor.execute('ALTER TABLE scan_history_new RENAME TO scan_history')
        print("   ✅ scan_history table recreated")
    else:
        # Add columns if they don't exist
        if 'gain_7d' not in columns:
            cursor.execute("ALTER TABLE scan_history ADD COLUMN gain_7d REAL DEFAULT 0")
            print("   ✅ Added gain_7d to scan_history")
        
        if 'gain_30d' not in columns:
            cursor.execute("ALTER TABLE scan_history ADD COLUMN gain_30d REAL DEFAULT 0")
            print("   ✅ Added gain_30d to scan_history")

def main():
    print("=" * 50)
    print("🔄 MIGRATING ALL TABLES")
    print("=" * 50)
    
    db_path = settings.db_paths['history']
    print(f"📁 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Migrate both tables
        migrate_active_coins(cursor)
        migrate_scan_history(cursor)
        
        conn.commit()
        print("\n✅ All migrations completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()