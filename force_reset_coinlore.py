#!/usr/bin/env python3
"""
Force reset CoinLore database with direct SQLite access
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.coinlore import CoinLoreClient
from config.settings import settings

def main():
    print("=" * 60)
    print("🔄 FORCE RESET COINLORE DATABASE")
    print("=" * 60)
    
    db_path = settings.db_paths['history']
    print(f"📁 Database: {db_path}")
    
    # Connect directly to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Drop and recreate table with correct schema
    print("\n🗑️  Dropping existing coin_list table...")
    cursor.execute('DROP TABLE IF EXISTS coin_list')
    
    print("✅ Creating new coin_list table...")
    cursor.execute('''
        CREATE TABLE coin_list (
            id TEXT PRIMARY KEY,
            symbol TEXT,
            name TEXT,
            rank INTEGER,
            last_updated TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX idx_coin_list_symbol ON coin_list(symbol)
    ''')
    conn.commit()
    print("✅ Table created successfully")
    
    # Initialize CoinLore client
    coinlore = CoinLoreClient()
    
    # Fetch all coins
    print("\n📡 Fetching all coins from CoinLore...")
    all_coins = coinlore.get_all_coins()
    
    if not all_coins:
        print("❌ Failed to fetch coins from CoinLore")
        conn.close()
        return
    
    print(f"✅ Got {len(all_coins)} coins from CoinLore")
    
    # Insert coins in batches
    print("\n💾 Inserting coins into database...")
    now = datetime.now().isoformat()
    batch_size = 500
    total_inserted = 0
    
    for i in range(0, len(all_coins), batch_size):
        batch = all_coins[i:i+batch_size]
        
        for coin in batch:
            try:
                cursor.execute('''
                    INSERT INTO coin_list (id, symbol, name, rank, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    str(coin.get('id')),
                    coin.get('symbol', '').lower(),
                    coin.get('name', ''),
                    coin.get('rank', 0),
                    now
                ))
                total_inserted += 1
            except Exception as e:
                print(f"   Error inserting coin {coin.get('symbol')}: {e}")
        
        conn.commit()
        print(f"   Inserted {total_inserted}/{len(all_coins)} coins...")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM coin_list")
    count = cursor.fetchone()[0]
    print(f"\n✅ Total coins in database after insertion: {count}")
    
    # Show sample
    cursor.execute("SELECT id, symbol FROM coin_list LIMIT 10")
    print("\n📋 Sample coins:")
    for row in cursor.fetchall():
        print(f"   ID: {row[0]}, Symbol: {row[1]}")
    
    # Test lookups
    test_symbols = ['btc', 'eth', 'sol', 'xrp', 'ada', 'doge']
    print(f"\n🔍 Testing lookups with lowercase: {test_symbols}")
    
    for symbol in test_symbols:
        cursor.execute("SELECT id FROM coin_list WHERE symbol = ?", (symbol,))
        result = cursor.fetchone()
        if result:
            print(f"   ✓ {symbol.upper()} found: ID={result[0]}")
        else:
            print(f"   ❌ {symbol.upper()} not found")
    
    conn.close()

if __name__ == "__main__":
    main()