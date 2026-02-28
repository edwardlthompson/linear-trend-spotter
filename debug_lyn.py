#!/usr/bin/env python3
"""
Debug script to check LYN price data directly from CoinGecko
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.coingecko import CoinGeckoClient
from database.cache import GeckoCache
from config.settings import settings
from processors.uniformity_filter import UniformityFilter

def main():
    print("=" * 60)
    print("🔍 LYN DEBUG TOOL")
    print("=" * 60)
    
    # Initialize clients
    gecko = CoinGeckoClient()
    cache = GeckoCache(settings.db_paths['history'])
    
    # Step 1: Check what gecko_id we have for LYN
    print("\n1. Checking cached gecko_id for LYN...")
    gecko_id = cache.get_gecko_id('LYN', 'Lyn')
    print(f"   Cached gecko_id: {gecko_id}")
    
    if not gecko_id:
        print("   ⚠️ No cached gecko_id found")
        # Try to find it by searching
        print("\n2. Searching for LYN on CoinGecko...")
        # You might need to implement a search function
        return
    
    # Step 2: Clear cached price data for LYN
    print(f"\n2. Clearing cached price data for {gecko_id}...")
    
    # Direct database access to clear cache
    import sqlite3
    conn = sqlite3.connect(settings.db_paths['history'])
    cursor = conn.cursor()
    
    # Check what's in the cache
    cursor.execute('''
        SELECT prices, uniformity_score, total_gain, cache_date 
        FROM price_cache WHERE gecko_id = ?
    ''', (gecko_id,))
    
    cached = cursor.fetchone()
    if cached:
        print(f"   Current cache: score={cached[1]}, gain={cached[2]:+.1f}%, date={cached[3]}")
        if cached[2] < 0:
            print("   ⚠️ Negative gain detected - this is WRONG based on CoinGecko data!")
    
    # Delete the cache
    cursor.execute('DELETE FROM price_cache WHERE gecko_id = ?', (gecko_id,))
    conn.commit()
    print("   ✅ Cache cleared")
    
    # Step 3: Fetch fresh data from CoinGecko
    print(f"\n3. Fetching fresh price data from CoinGecko for {gecko_id}...")
    prices = gecko.get_market_chart(gecko_id, 30)
    
    if not prices:
        print("   ❌ Failed to get price data")
        return
    
    print(f"   ✅ Got {len(prices)} price points")
    print(f"   First price: ${prices[0]:.8f}")
    print(f"   Last price: ${prices[-1]:.8f}")
    
    # Calculate base price and total gain
    base_price = prices[0]
    last_price = prices[-1]
    total_gain = ((last_price - base_price) / base_price) * 100
    
    print(f"\n4. Calculated metrics:")
    print(f"   Base price (30 days ago): ${base_price:.8f}")
    print(f"   Current price: ${last_price:.8f}")
    print(f"   Total gain: {total_gain:+.2f}%")
    
    # Calculate uniformity score
    score, gain = UniformityFilter.calculate(prices, 30)
    print(f"\n5. Uniformity calculation:")
    print(f"   Score: {score}/100")
    print(f"   Gain from filter: {gain:+.1f}%")
    
    # Step 6: Cache the correct data
    print(f"\n6. Caching correct data...")
    cache.cache_price_data(gecko_id, prices, score, total_gain)
    print(f"   ✅ Cached with score={score}, gain={total_gain:+.1f}%")
    
    # Step 7: Verify cache was updated
    needs_fetch, cached_data = cache.should_fetch_price_data(gecko_id)
    if cached_data:
        print(f"\n7. Cache verification:")
        print(f"   Stored score: {cached_data['uniformity_score']}")
        print(f"   Stored gain: {cached_data['total_gain']:+.1f}%")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ Debug complete! Run scheduler to see correct values.")
    print("=" * 60)

if __name__ == "__main__":
    main()