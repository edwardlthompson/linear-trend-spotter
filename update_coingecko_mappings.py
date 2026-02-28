#!/usr/bin/env python3
"""
Update CoinGecko mappings - run this periodically to refresh the mapping database
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.coingecko_mapper import CoinGeckoMapper
from config.settings import settings

def main():
    print("=" * 60)
    print("🔄 UPDATE COINGECKO MAPPINGS")
    print("=" * 60)
    
    db_path = settings.db_paths['history'].parent / 'coingecko_mappings.db'
    print(f"📁 Database: {db_path}")
    
    mapper = CoinGeckoMapper(db_path)
    
    # Update mappings
    added = mapper.update_mappings()
    
    if added > 0:
        print(f"\n✅ Successfully updated {added} mappings")
        
        # Show stats
        stats = mapper.get_stats()
        print(f"\n📊 Statistics:")
        print(f"   Total mappings: {stats['total_mappings']}")
        print(f"   Last updated: {stats['last_update']}")
        
        # Test a few symbols
        test_symbols = ['BTC', 'ETH', 'SOL', 'SIS', 'DAO', 'DCR']
        print(f"\n🔍 Testing lookups:")
        for symbol in test_symbols:
            coin_id = mapper.get_coin_id(symbol)
            if coin_id:
                print(f"   ✓ {symbol} -> {coin_id}")
            else:
                print(f"   ❌ {symbol} not found")
                mapper.debug_check_symbol(symbol)
    else:
        print("\n❌ Failed to update mappings")
    
    mapper.close()

if __name__ == "__main__":
    main()