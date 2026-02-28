#!/usr/bin/env python3
"""
Debug CoinLore API directly to see if it's returning data
"""

import requests
import json

def main():
    print("=" * 60)
    print("🔍 DEBUG COINLORE API DIRECTLY")
    print("=" * 60)
    
    # Test 1: Get first page of coins
    print("\n📡 Test 1: Fetching first page of coins...")
    url = "https://api.coinlore.net/api/tickers/?start=0&limit=10"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        coins = data.get('data', [])
        print(f"✅ Got {len(coins)} coins")
        
        if coins:
            print("\n📋 First 3 coins from API:")
            for coin in coins[:3]:
                print(f"   ID: {coin.get('id')}, Symbol: {coin.get('symbol')}, Name: {coin.get('name')}")
    else:
        print(f"❌ API error: {response.status_code}")
    
    # Test 2: Get Bitcoin specifically
    print("\n📡 Test 2: Fetching Bitcoin (ID 90)...")
    url = "https://api.coinlore.net/api/ticker/?id=90"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            coin = data[0]
            print(f"✅ Got Bitcoin:")
            print(f"   ID: {coin.get('id')}")
            print(f"   Symbol: {coin.get('symbol')}")
            print(f"   Name: {coin.get('name')}")
            print(f"   Rank: {coin.get('rank')}")
    else:
        print(f"❌ API error: {response.status_code}")

if __name__ == "__main__":
    main()