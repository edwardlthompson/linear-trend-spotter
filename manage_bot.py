#!/usr/bin/env python3
"""
Manage Telegram bot process
Usage: python3 manage_bot.py [start|stop|restart|status]
"""

import os
import sys
import signal
import subprocess
import time
import psutil
PID_FILE = 'bot.pid'
LOG_FILE = 'bot_output.log'


def _print_last_log_lines(path: str, max_lines: int = 5) -> None:
    """Print the last N lines of a log file without relying on Unix ``tail``."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            lines = handle.readlines()[-max_lines:]
    except OSError:
        return
    for line in lines:
        print(line.rstrip())


def get_pid():
    """Get PID from file"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None

def is_running(pid):
    """Check if process is running"""
    if not pid:
        return False
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False

def start():
    """Start the bot"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config.settings import settings

    if not settings.telegram_enabled:
        print("Telegram is disabled (DELIVERY_MODE=web or TELEGRAM_ENABLED=false). See docs/DELIVERY_MODE.md.")
        return

    pid = get_pid()
    if pid and is_running(pid):
        print(f"❌ Bot is already running with PID {pid}")
        return
    
    print("🚀 Starting bot...")
    with open(LOG_FILE, 'a') as log:
        process = subprocess.Popen(
            [sys.executable, 'telegram_bot.py'],
            stdout=log,
            stderr=log,
            start_new_session=True
        )
    
    with open(PID_FILE, 'w') as f:
        f.write(str(process.pid))
    
    print(f"✅ Bot started with PID {process.pid}")
    print(f"📝 Logs: {LOG_FILE} (last lines: manage_bot.py status)")

def stop():
    """Stop the bot"""
    pid = get_pid()
    if not pid:
        print("❌ No PID file found")
        return
    
    if not is_running(pid):
        print("❌ Bot is not running")
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return
    
    print(f"🛑 Stopping bot (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(2)
        if is_running(pid):
            os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    
    print("✅ Bot stopped")

def status():
    """Check bot status"""
    pid = get_pid()
    if pid and is_running(pid):
        print(f"✅ Bot is running with PID {pid}")
        # Show last few lines of log
        if os.path.exists(LOG_FILE):
            print("\n📝 Last 5 log lines:")
            _print_last_log_lines(LOG_FILE, 5)
    else:
        print("❌ Bot is not running")
        if pid:
            print("   (Stale PID file found)")

def restart():
    """Restart the bot"""
    stop()
    time.sleep(2)
    start()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 manage_bot.py [start|stop|restart|status]")
        sys.exit(1)
    
    command = sys.argv[1]
    if command == 'start':
        start()
    elif command == 'stop':
        stop()
    elif command == 'restart':
        restart()
    elif command == 'status':
        status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)