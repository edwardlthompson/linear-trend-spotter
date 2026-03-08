#!/usr/bin/env python3
"""
Migration script to add uniformity_score and total_gain columns to price_cache
Run this once to update your database schema
"""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

def migrate_price_cache():
    """Add new columns to price_cache table"""
    
    db_path = settings.db_paths['history']
    print(f"📁 Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns in price_cache
    cursor.execute("PRAGMA table_info(price_cache)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"📊 Current columns in price_cache: {columns}")
    
    # Add missing columns
    new_columns = [
        ('uniformity_score', 'REAL DEFAULT 0'),
        ('total_gain', 'REAL DEFAULT 0')
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE price_cache ADD COLUMN {col_name} {col_type}")
                print(f"✅ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Could not add {col_name}: {e}")
        else:
            print(f"⏭️ Column already exists: {col_name}")
    
    conn.commit()
    
    # Verify the update
    cursor.execute("PRAGMA table_info(price_cache)")
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
    
    # Check price_cache columns
    cursor.execute("PRAGMA table_info(price_cache)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"📊 price_cache columns: {columns}")
    
    required = ['uniformity_score', 'total_gain']
    missing = [col for col in required if col not in columns]
    
    if missing:
        print(f"❌ Missing columns: {missing}")
    else:
        print("✅ All required columns present")
    
    conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("🔄 MIGRATING PRICE CACHE DATABASE")
    print("=" * 50)
    
    migrate_price_cache()
    verify_schema()
    
    print("\n" + "=" * 50)
    print("✅ Migration complete! You can now run the scanner.")
    print("=" * 50)