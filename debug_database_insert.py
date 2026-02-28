#!/usr/bin/env python3
"""
Debug database insertion step by step
"""

import sys
import sqlite3
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.coinlore import CoinLoreClient
from config.settings import settings

def main():
    print("=" * 60)
    print("🔍 DEBUG DATABASE INSERTION")
    print("=" * 60)
    
    # Step 1: Check if we can get data from CoinLore
    print("\n📡 Step 1: Fetching data from CoinLore...")
    coinlore = CoinLoreClient()
    all_coins = coinlore.get_all_coins(limit=10)  # Just get first 10 for testing
    
    if not all_coins:
        print("❌ Failed to get coins from CoinLore")
        return
    
    print(f"✅ Got {len(all_coins)} coins from CoinLore")
    print(f"   First coin: {all_coins[0].get('symbol')} (ID: {all_coins[0].get('id')})")
    
    # Step 2: Connect to database directly
    print("\n💾 Step 2: Connecting to database...")
    db_path = settings.db_paths['history']
    print(f"   Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Step 3: Check if coin_list table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coin_list'")
    if not cursor.fetchone():
        print("❌ coin_list table does not exist")
        return
    print("✅ coin_list table exists")
    
    # Step 4: Insert a test coin manually
    print("\n📝 Step 4: Inserting test coin manually...")
    test_coin = all_coins[0]
    test_data = (
        str(test_coin.get('id')),
        test_coin.get('symbol', '').lower(),
        test_coin.get('name', ''),
        test_coin.get('rank', 0),
        '2024-01-01T00:00:00'
    )
    
    cursor.execute('''
        INSERT OR REPLACE INTO coin_list (id, symbol, name, rank, last_updated)
        VALUES (?, ?, ?, ?, ?)
    ''', test_data)
    conn.commit()
    print(f"✅ Inserted test coin: {test_coin.get('symbol')}")
    
    # Step 5: Verify insertion
    cursor.execute("SELECT COUNT(*) FROM coin_list")
    count = cursor.fetchone()[0]
    print(f"\n📊 Step 5: Total coins in database: {count}")
    
    if count > 0:
        cursor.execute("SELECT id, symbol, name FROM coin_list LIMIT 5")
        print("   Sample from database:")
        for row in cursor.fetchall():
            print(f"      ID: {row[0]}, Symbol: {row[1]}, Name: {row[2]}")
    
    conn.close()

if __name__ == "__main__":
    main()