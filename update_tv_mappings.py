#!/usr/bin/env python3
"""
Update TradingView symbol mappings
Run this periodically to add new coins
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.tradingview_mapper import TradingViewMapper
from config.settings import settings

def add_custom_mappings(mapper):
    """Add custom mappings for coins that failed"""
    
    # Add mappings for coins that previously failed
    custom_mappings = [
        # Format: (symbol, exchange, quote)
        ('PIPPIN', 'mexc', 'USDT'),
        ('GOAT', 'mexc', 'USDT'),
        ('FARTCOIN', 'mexc', 'USDT'),
        ('SPX', 'mexc', 'USDT'),
        ('POPCAT', 'mexc', 'USDT'),
        ('MOG', 'mexc', 'USDT'),
        ('BRETT', 'mexc', 'USDT'),
        ('TURBO', 'mexc', 'USDT'),
        ('COQ', 'mexc', 'USDT'),
        ('ANDY', 'mexc', 'USDT'),
        ('BOB', 'mexc', 'USDT'),
        ('HARRIS', 'mexc', 'USDT'),
        ('TRUMP', 'mexc', 'USDT'),
    ]
    
    for symbol, exchange, quote in custom_mappings:
        print(f"Adding mapping for {symbol} on {exchange}...")
        mapper.add_custom_mapping(symbol, exchange, quote)

def main():
    print("=" * 50)
    print("🔄 TRADINGVIEW MAPPING UPDATER")
    print("=" * 50)
    
    db_path = settings.db_paths['history'].parent / 'tv_mappings.db'
    print(f"📁 Database: {db_path}")
    
    mapper = TradingViewMapper(db_path)
    
    # Show current mappings
    mappings = mapper.get_all_mappings()
    print(f"\n📊 Current active mappings: {len(mappings)}")
    
    # Group by exchange
    by_exchange = {}
    for m in mappings:
        ex = m['exchange']
        if ex not in by_exchange:
            by_exchange[ex] = []
        by_exchange[ex].append(m['coin_symbol'])
    
    for ex, symbols in by_exchange.items():
        print(f"  {ex}: {len(symbols)} coins")
    
    # Add custom mappings
    print("\n🔄 Adding custom mappings...")
    add_custom_mappings(mapper)
    
    # Show updated counts
    mappings = mapper.get_all_mappings()
    print(f"\n✅ Total active mappings: {len(mappings)}")
    
    mapper.close()
    print("\n✅ Update complete!")

if __name__ == "__main__":
    main()