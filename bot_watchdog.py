#!/usr/bin/env python3
"""
Watchdog to ensure bot is running
Run this via cron every 5 minutes
"""

import os
import sys
import subprocess

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manage_bot import get_pid, is_running

def main():
    """Check if bot is running, start if not"""
    pid = get_pid()
    if not pid or not is_running(pid):
        print("Bot not running, starting...")
        subprocess.run(['python3', 'manage_bot.py', 'start'])
    else:
        print(f"Bot is running (PID {pid})")

if __name__ == "__main__":
    main()