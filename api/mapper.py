"""
Local mapping database interface
Provides fast lookup of CoinGecko IDs using the pre-built mapping database
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, Tuple
from config.settings import settings

class MappingDatabase:
    """
    Interface to the locally managed mapping database (mapping.db).
    This database is built separately using build_mapping_db.py and contains
    over 12,000 cryptocurrency mappings.
    """
    
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = Path(settings.BASE_DIR) / 'mapping.db'
        else:
            self.db_path = Path(db_path)
            
        self.connection = None
        self.available = self.db_path.exists()
        
        if self.available:
            try:
                self.connection = sqlite3.connect(str(self.db_path))
                # Test if table exists
                cursor = self.connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='symbol_mapping'")
                if not cursor.fetchone():
                    self.available = False
                    print(f"   ⚠️ Mapping database exists but has wrong schema at {self.db_path}")
                else:
                    # Get metadata
                    cursor.execute("SELECT value FROM mapping_metadata WHERE key='total_mappings'")
                    result = cursor.fetchone()
                    total = result[0] if result else 'unknown'
                    print(f"   ✓ Connected to mapping database ({total} mappings) at {self.db_path}")
            except Exception as e:
                self.available = False
                print(f"   ⚠️ Error connecting to mapping database: {e}")
        else:
            print(f"   ⚠️ Mapping database not found at {self.db_path}. Run build_mapping_db.py first.")
    
    def get_gecko_id(self, symbol: str, name: Optional[str] = None) -> Optional[str]:
        """
        Look up CoinGecko ID from the local mapping database.
        Returns gecko_id or None if not found.
        """
        if not self.available:
            return None
        
        try:
            cursor = self.connection.cursor()
            clean_symbol = symbol.upper().split('.')[0].split('-')[0]
            
            # Try exact symbol match first
            cursor.execute('''
                SELECT coingecko_id FROM symbol_mapping 
                WHERE symbol = ? ORDER BY confidence DESC LIMIT 1
            ''', (clean_symbol,))
            
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # If name is provided, try fuzzy match
            if name:
                cursor.execute('''
                    SELECT coingecko_id FROM symbol_mapping 
                    WHERE name LIKE ? OR ? LIKE name
                    ORDER BY confidence DESC LIMIT 1
                ''', (f'%{name}%', f'%{name}%'))
                
                result = cursor.fetchone()
                if result:
                    return result[0]
            
            return None
            
        except Exception as e:
            print(f"      ⚠️ Mapping lookup error: {e}")
            return None
    
    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()