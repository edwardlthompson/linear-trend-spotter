#!/usr/bin/env python3
"""
Fix symbol case in database - convert all to lowercase for consistency
"""

import sys
from pathlib import Path
import sqlite3

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

def main():
    print("=" * 60)
    print("🔄 FIX SYMBOL CASE IN DATABASE")
    print("=" * 60)
    
    db_path = settings.db_paths['history']
    print(f"📁 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First, show what we have
    cursor.execute("SELECT COUNT(*) FROM coin_list")
    total = cursor.fetchone()[0]
    print(f"\n📊 Total coins before fix: {total}")
    
    # Show sample before fix
    cursor.execute("SELECT id, symbol FROM coin_list LIMIT 5")
    print("\n📋 Sample before fix:")
    for row in cursor.fetchall():
        print(f"   ID: {row[0]}, Symbol: {row[1]}")
    
    # Update all symbols to lowercase
    cursor.execute("UPDATE coin_list SET symbol = LOWER(symbol)")
    conn.commit()
    
    print("\n✅ Updated all symbols to lowercase")
    
    # Show sample after fix
    cursor.execute("SELECT id, symbol FROM coin_list LIMIT 5")
    print("\n📋 Sample after fix:")
    for row in cursor.fetchall():
        print(f"   ID: {row[0]}, Symbol: {row[1]}")
    
    # Verify specific symbols
    test_symbols = ['btc', 'eth', 'sol']
    print("\n🎯 Verifying lookups:")
    for symbol in test_symbols:
        cursor.execute("SELECT id FROM coin_list WHERE symbol = ?", (symbol,))
        if cursor.fetchone():
            print(f"   ✓ {symbol.upper()} found")
        else:
            print(f"   ❌ {symbol.upper()} not found")
    
    conn.close()

if __name__ == "__main__":
    main()