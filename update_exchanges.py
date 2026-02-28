#!/usr/bin/env python3
"""
Simple script to update exchange listings
Run this manually or set up as a scheduled task
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchange_data.update_exchanges import main

if __name__ == "__main__":
    main()