#!/usr/bin/env python3
"""
Complete reset script - wipes all data and restarts everything fresh
"""

import os
import sqlite3
import time
import subprocess
import shutil
from pathlib import Path

def main():
    print("=" * 60)
    print("🔄 COMPLETE SYSTEM RESET")
    print("=" * 60)
    
    # Step 1: Stop the bot
    print("\n🛑 Stopping bot...")
    os.system("python3 manage_bot.py stop 2>/dev/null")
    time.sleep(2)
    
    # Step 2: Kill any remaining processes
    print("🔪 Killing any remaining processes...")
    os.system("pkill -f 'python3 telegram_bot.py' 2>/dev/null")
    os.system("pkill -f 'manage_bot.py' 2>/dev/null")
    os.system("rm -f bot.pid")
    time.sleep(1)
    
    # Step 3: Clear the active coins table
    print("🗑️  Clearing active coins from database...")
    conn = sqlite3.connect('history.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_coins;")
    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM active_coins").fetchone()[0]
    print(f"   Active coins now: {count}")
    conn.close()
    
    # Step 4: Clear the chart_debug folder
    print("🗑️  Clearing chart debug folder...")
    debug_dir = Path('chart_debug')
    if debug_dir.exists():
        shutil.rmtree(debug_dir)
        print(f"   Removed {debug_dir}")
    debug_dir.mkdir(exist_ok=True)
    print(f"   Created fresh {debug_dir}")
    
    # Step 5: Show current database state
    print("\n📊 Current database state:")
    print("-" * 40)
    conn = sqlite3.connect('history.db')
    cursor = conn.cursor()
    
    active = cursor.execute("SELECT COUNT(*) FROM active_coins").fetchone()[0]
    history = cursor.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
    cache = cursor.execute("SELECT COUNT(*) FROM coingecko_cache").fetchone()[0]
    price = cursor.execute("SELECT COUNT(*) FROM price_cache").fetchone()[0]
    
    print(f"Active coins:     {active}")
    print(f"Scan history:     {history}")
    print(f"Gecko cache:      {cache}")
    print(f"Price cache:      {price}")
    conn.close()
    print("-" * 40)
    
    # Step 6: Start the bot fresh
    print("\n🚀 Starting bot...")
    os.system("python3 manage_bot.py start")
    time.sleep(3)
    
    # Step 7: Check bot status
    print("\n🤖 Bot status:")
    os.system("python3 manage_bot.py status")
    
    # Step 8: Show recent logs
    print("\n📝 Recent bot logs:")
    print("-" * 40)
    if os.path.exists('bot_output.log'):
        os.system("tail -5 bot_output.log")
    else:
        print("No logs yet")
    print("-" * 40)
    
    # Step 9: Instructions
    print("\n" + "=" * 60)
    print("✅ READY FOR TESTING!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run a scan to generate new qualified coins:")
    print("   python3 scheduler.py")
    print("\n2. Watch for notifications on Telegram")
    print("\n3. Check chart_debug folder to verify charts were generated:")
    print("   ls -la chart_debug/")
    print("\n4. Monitor bot logs:")
    print("   tail -f bot_output.log")
    print("\n5. Check scan logs:")
    print("   tail -f trend_scanner.log")
    print("=" * 60)

if __name__ == "__main__":
    # Ask for confirmation
    print("\n⚠️  This will DELETE all active coins and reset the system!")
    response = input("Are you sure you want to continue? (yes/no): ")
    
    if response.lower() == 'yes':
        main()
    else:
        print("Reset cancelled.")