#!/usr/bin/env python3
"""
Script to update exchange listings database
Run this periodically (e.g., weekly) via cron
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from exchange_data.exchange_db import ExchangeDatabase
from exchange_data.exchange_fetcher import ExchangeFetcher
from config.settings import settings

def main():
    """Update all exchange listings"""
    print("=" * 50)
    print("🔄 EXCHANGE LISTINGS UPDATER")
    print("=" * 50)
    
    # Use history.db for exchange data (or create separate file)
    db_path = settings.db_paths['history'].parent / 'exchange_listings.db'
    print(f"📁 Database: {db_path}")
    
    # Initialize database
    db = ExchangeDatabase(db_path)
    fetcher = ExchangeFetcher(db)
    
    # Update all exchanges
    fetcher.update_all_exchanges()
    
    # Show stats
    stats = db.get_exchange_stats()
    print("\n📊 Exchange Statistics:")
    print("-" * 40)
    for exchange, data in stats.items():
        print(f"   {exchange.title()}:")
        print(f"      Last updated: {data['last_updated'][:10]}")
        print(f"      Total pairs: {data['total_pairs']}")
        print(f"      Source: {data['source']}")
    
    db.close()
    print("\n✅ Update complete!")

if __name__ == "__main__":
    main()