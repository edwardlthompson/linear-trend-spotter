#!/usr/bin/env python3
"""
Test CoinLore ID lookup
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database.cache import CoinLoreCache
from config.settings import settings

def main():
    print("=" * 60)
    print("🔍 TEST COINLORE LOOKUP")
    print("=" * 60)
    
    cache = CoinLoreCache(settings.db_paths['history'])
    
    # First show what's in the database
    total = cache.debug_coin_list()
    
    if total == 0:
        print("\n❌ Database is empty! Please run force_reset_coinlore.py first")
        cache.close()
        return
    
    # Test symbols with mixed case
    test_symbols = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE']
    
    print(f"\n🎯 Testing lookups for: {test_symbols}")
    
    id_map = cache.get_coin_ids_batch(test_symbols)
    
    print(f"\n📊 Results: Found {len(id_map)} out of {len(test_symbols)}")
    
    for symbol in test_symbols:
        if symbol in id_map:
            print(f"   ✓ {symbol} -> ID: {id_map[symbol]}")
        else:
            print(f"   ❌ {symbol} not found")
    
    cache.close()

if __name__ == "__main__":
    main()