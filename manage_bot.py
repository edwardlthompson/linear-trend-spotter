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

def get_pid():
    """Get PID from file"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except:
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
    pid = get_pid()
    if pid and is_running(pid):
        print(f"❌ Bot is already running with PID {pid}")
        return
    
    print("🚀 Starting bot...")
    with open(LOG_FILE, 'a') as log:
        process = subprocess.Popen(
            ['python3', 'telegram_bot.py'],
            stdout=log,
            stderr=log,
            start_new_session=True
        )
    
    with open(PID_FILE, 'w') as f:
        f.write(str(process.pid))
    
    print(f"✅ Bot started with PID {process.pid}")
    print(f"📝 Logs: tail -f {LOG_FILE}")

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
    except:
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
            try:
                subprocess.run(['tail', '-5', LOG_FILE])
            except:
                # Fallback if tail command fails
                with open(LOG_FILE, 'r') as f:
                    lines = f.readlines()[-5:]
                    for line in lines:
                        print(line.rstrip())
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