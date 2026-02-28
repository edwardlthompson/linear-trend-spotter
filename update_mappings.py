#!/usr/bin/env python3
"""
Simplified update script for TradingView mappings
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api.tradingview_mapper import TradingViewMapper
from config.settings import settings

def main():
    print("=" * 50)
    print("🔄 UPDATE TRADINGVIEW MAPPINGS")
    print("=" * 50)
    
    db_path = settings.db_paths['history'].parent / 'tv_mappings.db'
    
    # Remove old database
    if db_path.exists():
        print("🗑️  Removing old database...")
        db_path.unlink()
    
    # Create fresh mapper (will create new database)
    mapper = TradingViewMapper(db_path)
    
    # Add custom mappings for meme coins
    print("\n🔄 Adding meme coin mappings...")
    
    meme_coins = [
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
    
    for symbol, exchange, quote in meme_coins:
        print(f"  Adding {symbol} on {exchange}...")
        mapper.add_custom_mapping(symbol, exchange, quote)
    
    print("\n✅ Update complete!")
    mapper.close()

if __name__ == "__main__":
    main()