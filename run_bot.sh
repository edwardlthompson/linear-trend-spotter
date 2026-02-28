#!/bin/bash
# Script to run Telegram bot in background
# Run this once after scanner is set up

cd /home/edwardlthompson/mysite

# Kill any existing bot process
pkill -f "python3 telegram_bot.py" 2>/dev/null

# Wait a moment
sleep 2

# Start bot in background with nohup
nohup python3 telegram_bot.py > bot_output.log 2>&1 &

echo "✅ Telegram bot started with PID $!"
echo "📝 Logs: tail -f bot_output.log"
echo "📝 To stop: pkill -f 'python3 telegram_bot.py'"