#!/usr/bin/env python3
"""
Migration script to add coinlore_id column to active_coins table
Run this once to update your database schema
"""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

def migrate_active_coins():
    """Add coinlore_id column to active_coins table"""
    
    db_path = settings.db_paths['history']
    print(f"📁 Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns in active_coins
    cursor.execute("PRAGMA table_info(active_coins)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"📊 Current columns in active_coins: {columns}")
    
    # Add coinlore_id column if it doesn't exist
    if 'coinlore_id' not in columns:
        try:
            cursor.execute("ALTER TABLE active_coins ADD COLUMN coinlore_id TEXT")
            print("✅ Added column: coinlore_id")
        except sqlite3.OperationalError as e:
            print(f"⚠️ Could not add coinlore_id: {e}")
    else:
        print("⏭️ Column already exists: coinlore_id")
    
    # Also check if gecko_id exists (it should, but just in case)
    if 'gecko_id' not in columns:
        try:
            cursor.execute("ALTER TABLE active_coins ADD COLUMN gecko_id TEXT")
            print("✅ Added column: gecko_id")
        except sqlite3.OperationalError as e:
            print(f"⚠️ Could not add gecko_id: {e}")
    
    conn.commit()
    
    # Verify the update
    cursor.execute("PRAGMA table_info(active_coins)")
    updated_columns = [col[1] for col in cursor.fetchall()]
    print(f"\n📊 Updated columns: {updated_columns}")
    
    conn.close()
    
    print("\n✅ Migration complete!")

def verify_schema():
    """Verify the migration was successful"""
    db_path = settings.db_paths['history']
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n🔍 Verifying migration...")
    
    # Check active_coins columns
    cursor.execute("PRAGMA table_info(active_coins)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"📊 active_coins columns: {columns}")
    
    required = ['coin_symbol', 'coin_name', 'gecko_id', 'coinlore_id', 'entered_date', 
                'last_seen_date', 'last_scan_date', 'total_gain', 'norm_slope',
                'coinbase_volume', 'kraken_volume', 'mexc_volume', 'slug', 'cmc_url']
    
    missing = [col for col in required if col not in columns]
    if missing:
        print(f"❌ Missing columns: {missing}")
    else:
        print("✅ All required columns present")
    
    conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("🔄 MIGRATING ACTIVE_COINS TABLE")
    print("=" * 50)
    
    migrate_active_coins()
    verify_schema()
    
    print("\n" + "=" * 50)
    print("✅ Migration complete! You can now run the scanner.")
    print("=" * 50)