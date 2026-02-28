#!/usr/bin/env python3
"""
Migration script to add new columns to cache tables
Run this once to update your database schema
"""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

def migrate_cache_db():
    """Add new columns to cache tables"""
    db_path = settings.db_paths['history']
    print(f"📁 Migrating cache database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(gecko_cache)")
    columns = [col[1] for col in cursor.fetchall()]
    
    migrations_needed = []
    
    if 'failure_count' not in columns:
        migrations_needed.append("ADD COLUMN failure_count INTEGER DEFAULT 0")
    
    if 'last_failure' not in columns:
        migrations_needed.append("ADD COLUMN last_failure TEXT")
    
    if migrations_needed:
        print(f"🔄 Adding {len(migrations_needed)} new columns...")
        for migration in migrations_needed:
            try:
                cursor.execute(f"ALTER TABLE gecko_cache {migration}")
                print(f"   ✓ {migration}")
            except sqlite3.OperationalError as e:
                print(f"   ⚠️ {e}")
    else:
        print("✅ All columns already exist")
    
    # Create stats table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache_stats (
            metric TEXT PRIMARY KEY,
            value INTEGER,
            last_updated TEXT
        )
    ''')
    
    # Initialize stats
    metrics = ['cache_hits', 'cache_misses', 'api_calls', 'failed_fetches']
    from datetime import datetime
    now = datetime.now().isoformat()
    
    for metric in metrics:
        cursor.execute('''
            INSERT OR IGNORE INTO cache_stats (metric, value, last_updated)
            VALUES (?, 0, ?)
        ''', (metric, now))
    
    conn.commit()
    conn.close()
    
    print("\n✅ Migration complete!")
    print("   You can now run the scanner with the enhanced cache.")

if __name__ == "__main__":
    migrate_cache_db()