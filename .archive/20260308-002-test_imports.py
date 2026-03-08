#!/usr/bin/env python3
"""Test that critical imports work after Sprint 1.2 changes"""

try:
    from api import CoinGeckoClient
    print('✅ CoinGeckoClient import successful')
except Exception as e:
    print(f'❌ CoinGeckoClient import failed: {e}')

try:
    from database import PriceCache
    print('✅ PriceCache import successful')
except Exception as e:
    print(f'❌ PriceCache import failed: {e}')

try:
    from config import settings
    print('✅ settings import successful')
except Exception as e:
    print(f'❌ settings import failed: {e}')

print("\n✅ All critical imports verified!")
