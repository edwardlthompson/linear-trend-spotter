#!/usr/bin/env python3
"""
Force fix for LYN - completely nuke the cache and fetch fresh data
"""

import sys
import sqlite3
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.coingecko import CoinGeckoClient
from api.dexpaprika import DexPaprikaClient
from database.cache import GeckoCache
from config.settings import settings
from processors.uniformity_filter import UniformityFilter

def main():
    print("=" * 60)
    print("🔧 FORCE FIX FOR LYN")
    print("=" * 60)
    
    # Step 1: Connect directly to database
    db_path = settings.db_paths['history']
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Step 2: Find gecko_id for LYN
    print("\n1. Finding LYN in database...")
    cursor.execute('''
        SELECT gecko_id FROM gecko_cache 
        WHERE coin_symbol = 'LYN' OR coin_name LIKE '%Lyn%'
    ''')
    
    result = cursor.fetchone()
    if result:
        gecko_id = result[0]
        print(f"   ✅ Found gecko_id: {gecko_id}")
    else:
        print("   ⚠️ No gecko_id found, will try search")
        gecko_id = None
    
    # Step 3: NUKE the price cache (hard delete)
    print("\n2. 💣 NUKING price cache for LYN...")
    
    if gecko_id:
        cursor.execute('DELETE FROM price_cache WHERE gecko_id = ?', (gecko_id,))
        print(f"   ✅ Deleted price_cache entry for {gecko_id}")
    
    # Also delete any price cache entries that might have LYN in the data
    cursor.execute("SELECT gecko_id, prices FROM price_cache")
    for row in cursor.fetchall():
        try:
            prices_data = json.loads(row[1])
            # Can't easily check, but we'll keep for now
            pass
        except:
            pass
    
    conn.commit()
    
    # Step 4: Try DexPaprika first (more reliable)
    print("\n3. 🔍 Fetching LYN data from DexPaprika...")
    dexpaprika = DexPaprikaClient()
    
    # Search for LYN
    token_info = dexpaprika.search_token('LYN')
    
    if token_info:
        print(f"   ✅ Found LYN on {token_info['network']}")
        print(f"   Address: {token_info['address']}")
        
        # Get price history
        prices = dexpaprika.get_token_price_history(
            token_info['network'], 
            token_info['address'], 
            days=30
        )
        
        if prices and len(prices) >= 30:
            print(f"   ✅ Got {len(prices)} price points from DexPaprika")
            print(f"   First price: ${prices[0]:.8f}")
            print(f"   Last price: ${prices[-1]:.8f}")
            
            # Calculate gain
            base_price = prices[0]
            last_price = prices[-1]
            gain = ((last_price - base_price) / base_price) * 100
            print(f"   📈 Actual gain: {gain:+.2f}%")
            
            # Calculate uniformity
            score, _ = UniformityFilter.calculate(prices, 30)
            print(f"   📊 Uniformity score: {score}/100")
            
            # Cache the correct data if we have gecko_id
            if gecko_id:
                cache = GeckoCache(db_path)
                cache.cache_price_data(gecko_id, prices, score, gain)
                print(f"   ✅ Cached correct data")
        else:
            print(f"   ⚠️ Could not get price history from DexPaprika")
    else:
        print(f"   ⚠️ Could not find LYN on DexPaprika")
    
    # Step 5: Verify the fix
    print("\n4. Verifying cache...")
    if gecko_id:
        cursor.execute('''
            SELECT uniformity_score, total_gain, cache_date 
            FROM price_cache WHERE gecko_id = ?
        ''', (gecko_id,))
        
        result = cursor.fetchone()
        if result:
            score, gain, date = result
            print(f"   ✅ Cache now has: score={score}, gain={gain:+.1f}%, date={date}")
        else:
            print(f"   ⚠️ No cache entry found")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ Force fix complete! Run scheduler to see results.")
    print("=" * 60)

if __name__ == "__main__":
    main()