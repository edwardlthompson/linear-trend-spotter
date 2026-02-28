#!/usr/bin/env python3
"""
Clear corrupted price cache data for specific coins
Run this to force refresh of price data
"""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

def clear_price_cache(coin_symbols=None):
    """
    Clear price cache for specific coins or all coins
    
    Args:
        coin_symbols: List of coin symbols to clear (None = clear all)
    """
    db_path = settings.db_paths['history']
    print(f"📁 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if coin_symbols:
        # Clear specific coins
        placeholders = ','.join(['?'] * len(coin_symbols))
        
        # First, find gecko_ids for these symbols
        cursor.execute(f'''
            SELECT gecko_id FROM gecko_cache 
            WHERE coin_symbol IN ({placeholders})
        ''', coin_symbols)
        
        gecko_ids = [row[0] for row in cursor.fetchall()]
        
        if gecko_ids:
            id_placeholders = ','.join(['?'] * len(gecko_ids))
            cursor.execute(f'''
                DELETE FROM price_cache 
                WHERE gecko_id IN ({id_placeholders})
            ''', gecko_ids)
            
            print(f"✅ Cleared price cache for {len(gecko_ids)} coins: {', '.join(coin_symbols)}")
        else:
            print(f"⚠️ No gecko_ids found for symbols: {', '.join(coin_symbols)}")
    else:
        # Clear all price cache
        cursor.execute('DELETE FROM price_cache')
        print("✅ Cleared ALL price cache data")
    
    conn.commit()
    conn.close()

def verify_cache():
    """Check what's in the price cache"""
    db_path = settings.db_paths['history']
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n📊 Current Price Cache Status:")
    print("-" * 50)
    
    cursor.execute('''
        SELECT p.gecko_id, g.coin_symbol, p.uniformity_score, p.total_gain, p.cache_date
        FROM price_cache p
        LEFT JOIN gecko_cache g ON p.gecko_id = g.gecko_id
        ORDER BY p.cache_date DESC
        LIMIT 10
    ''')
    
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            gecko_id, symbol, score, gain, cache_date = row
            print(f"   {symbol or gecko_id}: score={score}, gain={gain:+.1f}%, cached={cache_date[:16]}")
    else:
        print("   No cached price data")
    
    conn.close()

def main():
    print("=" * 50)
    print("🔄 CLEAR PRICE CACHE")
    print("=" * 50)
    
    # Show current cache before clearing
    verify_cache()
    
    print("\n")
    
    # Clear cache for LYN specifically
    clear_price_cache(['LYN'])
    
    # Also clear for any other coins you suspect have bad data
    # clear_price_cache(['POWER', 'SIGMA'])
    
    print("\n")
    
    # Show cache after clearing
    verify_cache()
    
    print("\n" + "=" * 50)
    print("✅ Cache cleared! Run scheduler to refresh data.")
    print("=" * 50)

if __name__ == "__main__":
    main()