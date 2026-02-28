#!/usr/bin/env python3
"""
Reset CoinLore database and fetch fresh data
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.coinlore import CoinLoreClient
from database.cache import CoinLoreCache
from config.settings import settings

def main():
    print("=" * 60)
    print("🔄 RESET COINLORE DATABASE")
    print("=" * 60)
    
    # Initialize
    print("\n📁 Initializing database with correct schema...")
    cache = CoinLoreCache(settings.db_paths['history'])
    coinlore = CoinLoreClient()
    
    # Fetch fresh data
    print("\n📡 Fetching fresh data from CoinLore...")
    all_coins = coinlore.get_all_coins()
    
    if not all_coins:
        print("❌ Failed to fetch coins")
        return
    
    print(f"✅ Got {len(all_coins)} coins")
    
    # Format for database
    formatted_coins = []
    for coin in all_coins:
        formatted_coins.append({
            'coin_id': str(coin.get('id')),
            'symbol': coin.get('symbol', '').upper(),
            'name': coin.get('name', ''),
            'rank': coin.get('rank', 0)
        })
    
    # Insert into database
    print("\n💾 Inserting into database...")
    added = cache.update_coin_list(formatted_coins)
    print(f"✅ Added {added} coins")
    
    # Verify
    print("\n🔍 Verifying...")
    total = cache.debug_coin_list()
    print(f"\n✅ Database now has {total} coins")
    
    cache.close()

if __name__ == "__main__":
    main()