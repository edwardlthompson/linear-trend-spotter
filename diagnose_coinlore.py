#!/usr/bin/env python3
"""
Diagnostic script to check CoinLore database
Run this first to see what's wrong
"""

import sqlite3
from pathlib import Path

def main():
    print("=" * 60)
    print("🔍 COINLORE DATABASE DIAGNOSTIC")
    print("=" * 60)
    
    db_path = Path(__file__).parent / 'history.db'
    print(f"📁 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if coin_list table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coin_list'")
    if not cursor.fetchone():
        print("❌ coin_list table does not exist!")
        conn.close()
        return
    
    print("✅ coin_list table exists")
    
    # Count records
    cursor.execute("SELECT COUNT(*) FROM coin_list")
    count = cursor.fetchone()[0]
    print(f"📊 Total records in coin_list: {count}")
    
    if count == 0:
        print("❌ coin_list table is empty!")
        conn.close()
        return
    
    # Show sample records
    print("\n📋 Sample records (first 10):")
    cursor.execute("SELECT id, symbol, name FROM coin_list LIMIT 10")
    rows = cursor.fetchall()
    for row in rows:
        print(f"   ID: {row[0]}, Symbol: {row[1]}, Name: {row[2]}")
    
    # Check for numeric IDs
    print("\n🔢 Checking ID formats:")
    cursor.execute("SELECT id FROM coin_list LIMIT 20")
    ids = cursor.fetchall()
    numeric_count = 0
    non_numeric_count = 0
    for id_tuple in ids:
        id_val = id_tuple[0]
        if id_val.isdigit():
            numeric_count += 1
        else:
            non_numeric_count += 1
            print(f"   Non-numeric ID found: {id_val}")
    
    print(f"   Numeric IDs: {numeric_count}")
    print(f"   Non-numeric IDs: {non_numeric_count}")
    
    # Test a specific symbol lookup
    test_symbols = ['BTC', 'ETH', 'SOL', 'XRP']
    print("\n🎯 Testing symbol lookups:")
    for symbol in test_symbols:
        cursor.execute("SELECT id FROM coin_list WHERE symbol = ?", (symbol.lower(),))
        result = cursor.fetchone()
        if result:
            print(f"   ✓ {symbol} -> ID: {result[0]}")
        else:
            print(f"   ❌ {symbol} not found")
    
    conn.close()

if __name__ == "__main__":
    main()