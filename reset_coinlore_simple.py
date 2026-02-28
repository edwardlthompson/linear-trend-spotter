#!/usr/bin/env python3
"""
Simple reset that just gets coins and inserts them directly
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
    print("🔄 SIMPLE COINLORE RESET")
    print("=" * 60)
    
    # Initialize
    coinlore = CoinLoreClient()
    db_path = settings.db_paths['history']
    
    print(f"📁 Database: {db_path}")
    
    # Connect directly
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coin_list (
            id TEXT PRIMARY KEY,
            symbol TEXT,
            name TEXT,
            rank INTEGER,
            last_updated TEXT
        )
    ''')
    
    # Clear existing data
    cursor.execute('DELETE FROM coin_list')
    print("✅ Cleared existing data")
    
    # Fetch coins
    print("\n📡 Fetching coins from CoinLore...")
    all_coins = coinlore.get_all_coins()
    
    if not all_coins:
        print("❌ Failed to fetch coins")
        conn.close()
        return
    
    print(f"✅ Got {len(all_coins)} coins")
    
    # Insert coins
    print("\n💾 Inserting coins into database...")
    now = datetime.now().isoformat()
    inserted = 0
    
    for coin in all_coins:
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
            inserted += 1
            
            # Print progress every 1000 coins
            if inserted % 1000 == 0:
                print(f"   Inserted {inserted} coins...")
                
        except Exception as e:
            print(f"   Error inserting coin {coin.get('symbol')}: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} coins")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM coin_list")
    count = cursor.fetchone()[0]
    print(f"\n📊 Total coins in database: {count}")
    
    if count > 0:
        cursor.execute("SELECT id, symbol FROM coin_list LIMIT 10")
        print("   Sample coins:")
        for row in cursor.fetchall():
            print(f"      ID: {row[0]}, Symbol: {row[1]}")
    
    conn.close()

if __name__ == "__main__":
    main()