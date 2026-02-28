#!/usr/bin/env python3
"""
Debug script to see what symbols are actually in the database
"""

import sys
from pathlib import Path
import sqlite3

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

def main():
    print("=" * 60)
    print("🔍 DEBUG SYMBOLS IN DATABASE")
    print("=" * 60)
    
    db_path = settings.db_paths['history']
    print(f"📁 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if coin_list exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coin_list'")
    if not cursor.fetchone():
        print("❌ coin_list table does not exist!")
        return
    
    # Count total coins
    cursor.execute("SELECT COUNT(*) FROM coin_list")
    total = cursor.fetchone()[0]
    print(f"\n📊 Total coins in database: {total}")
    
    if total == 0:
        print("❌ Database is empty!")
        return
    
    # Show sample of what's in the database
    print("\n📋 Sample of coins in database (first 20):")
    cursor.execute("SELECT id, symbol, name FROM coin_list LIMIT 20")
    rows = cursor.fetchall()
    for row in rows:
        print(f"   ID: {row[0]}, Symbol: {row[1]}, Name: {row[2]}")
    
    # Check specifically for BTC
    print("\n🎯 Looking for specific symbols:")
    test_symbols = ['btc', 'eth', 'sol', 'xrp', 'ada', 'doge']
    
    for symbol in test_symbols:
        cursor.execute("SELECT id, name FROM coin_list WHERE symbol = ?", (symbol,))
        result = cursor.fetchone()
        if result:
            print(f"   ✓ {symbol.upper()} found: ID={result[0]}, Name={result[1]}")
        else:
            print(f"   ❌ {symbol.upper()} not found")
    
    # Show symbol distribution
    print("\n📊 Symbol format analysis:")
    cursor.execute("SELECT symbol FROM coin_list LIMIT 100")
    symbols = [row[0] for row in cursor.fetchall()]
    
    lowercase_count = sum(1 for s in symbols if s.islower())
    uppercase_count = sum(1 for s in symbols if s.isupper())
    mixed_count = len(symbols) - lowercase_count - uppercase_count
    
    print(f"   Lowercase symbols: {lowercase_count}")
    print(f"   Uppercase symbols: {uppercase_count}")
    print(f"   Mixed case symbols: {mixed_count}")
    
    conn.close()

if __name__ == "__main__":
    main()