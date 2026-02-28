#!/usr/bin/env python3
"""
CoinGecko Mapping Database Builder
Run this script periodically (e.g., monthly) to update the mapping database.
Uses free public resources to build a comprehensive mapping.
"""

import json
import sqlite3
import requests
import time
from datetime import datetime
import os
import sys

# Get the absolute path to the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPING_DB_PATH = os.path.join(BASE_DIR, 'mapping.db')

print(f"📁 Base directory: {BASE_DIR}")
print(f"📁 Mapping DB will be created at: {MAPPING_DB_PATH}")

def download_cryptocurrency_list():
    """
    Download the comprehensive cryptocurrency list from the cryptocurrencies package.
    This is a free, open-source resource with 12,000+ entries.
    """
    print("📥 Downloading cryptocurrency list...")
    
    # Primary source: cryptocurrencies.json from GitHub (free, open-source)
    url = "https://raw.githubusercontent.com/crypti/cryptocurrencies/master/cryptocurrencies.json"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"   ✓ Downloaded {len(data)} cryptocurrency entries")
        return data
    except Exception as e:
        print(f"   ✗ Error downloading: {e}")
        return None

def fetch_coingecko_coin_list():
    """
    Fetch the complete coin list from CoinGecko's public API.
    This is a free endpoint that returns all supported coins.
    """
    print("📥 Fetching CoinGecko coin list...")
    
    url = "https://api.coingecko.com/api/v3/coins/list"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"   ✓ Fetched {len(data)} coins from CoinGecko")
        return data
    except Exception as e:
        print(f"   ✗ Error fetching: {e}")
        return None

def build_mapping_database(crypto_data, gecko_data):
    """
    Build a SQLite database mapping symbols to CoinGecko IDs.
    Uses multiple strategies to create the most accurate mapping.
    """
    conn = sqlite3.connect(MAPPING_DB_PATH)
    cursor = conn.cursor()
    
    # Create mapping tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS symbol_mapping (
            symbol TEXT,
            name TEXT,
            coingecko_id TEXT,
            confidence INTEGER,
            source TEXT,
            last_updated TEXT,
            PRIMARY KEY (symbol, name)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mapping_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Clear existing data
    cursor.execute('DELETE FROM symbol_mapping')
    
    # Create index for fast lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON symbol_mapping(symbol)')
    
    # Build a lookup dictionary from CoinGecko data
    gecko_dict = {}
    for coin in gecko_data:
        symbol = coin['symbol'].upper()
        if symbol not in gecko_dict:
            gecko_dict[symbol] = []
        gecko_dict[symbol].append({
            'id': coin['id'],
            'name': coin['name']
        })
    
    # Strategy 1: Map using cryptocurrency list (high confidence)
    print("   Building mappings from cryptocurrency list...")
    mapped_count = 0
    
    for symbol, name in crypto_data.items():
        symbol_upper = symbol.upper()
        
        if symbol_upper in gecko_dict:
            # Found matching symbol in CoinGecko
            matches = gecko_dict[symbol_upper]
            
            if len(matches) == 1:
                # Single match - high confidence
                cursor.execute('''
                    INSERT OR REPLACE INTO symbol_mapping 
                    (symbol, name, coingecko_id, confidence, source, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol_upper, name, matches[0]['id'], 90, 'cryptocurrencies', 
                      datetime.now().isoformat()))
                mapped_count += 1
            else:
                # Multiple matches - try to match by name
                for match in matches:
                    if name.lower() in match['name'].lower() or match['name'].lower() in name.lower():
                        cursor.execute('''
                            INSERT OR REPLACE INTO symbol_mapping 
                            (symbol, name, coingecko_id, confidence, source, last_updated)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (symbol_upper, name, match['id'], 85, 'cryptocurrencies+name', 
                              datetime.now().isoformat()))
                        mapped_count += 1
                        break
    
    print(f"   ✓ Mapped {mapped_count} symbols from cryptocurrency list")
    
    # Strategy 2: Add any remaining CoinGecko coins with lower confidence
    print("   Adding remaining CoinGecko coins...")
    remaining = 0
    
    for symbol, matches in gecko_dict.items():
        for match in matches:
            # Check if already mapped
            cursor.execute('SELECT COUNT(*) FROM symbol_mapping WHERE symbol = ? AND coingecko_id = ?',
                         (symbol, match['id']))
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT OR REPLACE INTO symbol_mapping 
                    (symbol, name, coingecko_id, confidence, source, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, match['name'], match['id'], 70, 'coingecko_direct',
                      datetime.now().isoformat()))
                remaining += 1
    
    print(f"   ✓ Added {remaining} additional CoinGecko mappings")
    
    # Store metadata
    cursor.execute('''
        INSERT OR REPLACE INTO mapping_metadata (key, value)
        VALUES (?, ?)
    ''', ('last_updated', datetime.now().isoformat()))
    
    cursor.execute('''
        INSERT OR REPLACE INTO mapping_metadata (key, value)
        VALUES (?, ?)
    ''', ('total_mappings', mapped_count + remaining))
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Mapping database built successfully!")
    print(f"   Total mappings: {mapped_count + remaining}")
    print(f"   Database: {MAPPING_DB_PATH}")

def main():
    print("="*50)
    print("🔧 COINGECKO MAPPING DATABASE BUILDER")
    print("="*50)
    print(f"Working directory: {BASE_DIR}")
    
    # Step 1: Download cryptocurrency list
    crypto_data = download_cryptocurrency_list()
    if not crypto_data:
        print("❌ Failed to download cryptocurrency list")
        return
    
    # Step 2: Fetch CoinGecko coin list
    gecko_data = fetch_coingecko_coin_list()
    if not gecko_data:
        print("❌ Failed to fetch CoinGecko list")
        return
    
    # Step 3: Build the mapping database
    build_mapping_database(crypto_data, gecko_data)
    
    print("\n✨ Done! You can now use mapping.db with your main application.")
    print(f"   Next step: Run python {os.path.join(BASE_DIR, 'main.py')}")

if __name__ == "__main__":
    main()