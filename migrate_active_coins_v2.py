#!/usr/bin/env python3
"""
Migration script to update active_coins table with gain_7d and gain_30d columns
Run this once to update your database schema
"""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

def migrate_active_coins():
    """Update active_coins table with new gain columns"""
    
    db_path = settings.db_paths['history']
    print(f"📁 Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns in active_coins
    cursor.execute("PRAGMA table_info(active_coins)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"📊 Current columns in active_coins: {columns}")
    
    # Drop old total_gain column if it exists
    if 'total_gain' in columns:
        # SQLite doesn't support dropping columns directly, so we need to recreate the table
        print("🔄 Recreating table with new schema...")
        
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
        
        # Copy data from old table, mapping old columns to new ones
        # Map total_gain to gain_30d (as best we can)
        cursor.execute('''
            INSERT INTO active_coins_new 
            SELECT 
                coin_symbol, coin_name, gecko_id, coinlore_id, entered_date, last_seen_date, last_scan_date,
                0 as gain_7d,  -- Default value
                total_gain as gain_30d,
                norm_slope,
                coinbase_volume, kraken_volume, mexc_volume, slug, cmc_url
            FROM active_coins
        ''')
        
        # Drop old table and rename new one
        cursor.execute('DROP TABLE active_coins')
        cursor.execute('ALTER TABLE active_coins_new RENAME TO active_coins')
        
        print("✅ Table recreated with new columns")
        
    else:
        # Add new columns if they don't exist
        if 'gain_7d' not in columns:
            cursor.execute("ALTER TABLE active_coins ADD COLUMN gain_7d REAL DEFAULT 0")
            print("✅ Added column: gain_7d")
        
        if 'gain_30d' not in columns:
            cursor.execute("ALTER TABLE active_coins ADD COLUMN gain_30d REAL DEFAULT 0")
            print("✅ Added column: gain_30d")
        
        # Drop old total_gain if it exists (SQLite doesn't support drop column, so we'd need recreate)
        if 'total_gain' in columns:
            print("⚠️ Note: total_gain column still exists but won't be used")
    
    conn.commit()
    
    # Verify the update
    cursor.execute("PRAGMA table_info(active_coins)")
    updated_columns = [col[1] for col in cursor.fetchall()]
    print(f"\n📊 Updated columns: {updated_columns}")
    
    required = ['gain_7d', 'gain_30d']
    missing = [col for col in required if col not in updated_columns]
    if missing:
        print(f"❌ Missing columns: {missing}")
    else:
        print("✅ All required columns present")
    
    conn.close()
    
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    print("=" * 50)
    print("🔄 MIGRATING ACTIVE_COINS TABLE V2")
    print("=" * 50)
    
    migrate_active_coins()
    
    print("\n" + "=" * 50)
    print("✅ Migration complete! You can now run the scanner.")
    print("=" * 50)