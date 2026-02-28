#!/bin/bash
# Complete reset and run script - combines all steps

echo "========================================="
echo "🔄 COMPLETE SYSTEM RESET AND RUN"
echo "========================================="
echo "Started: $(date)"
echo ""

cd /home/edwardlthompson/mysite

# Step 1: Stop the bot
echo "🛑 Stopping bot..."
python3 manage_bot.py stop 2>/dev/null
sleep 2

# Step 2: Kill any remaining processes
echo "🔪 Killing any remaining processes..."
pkill -f "python3 telegram_bot.py" 2>/dev/null
pkill -f "manage_bot.py" 2>/dev/null
rm -f bot.pid
echo "✅"

# Step 3: Clear the active coins table
echo "🗑️  Clearing active coins from database..."
sqlite3 history.db "DELETE FROM active_coins;"
echo "✅"

# Step 4: Clear the scan history (optional)
echo "🗑️  Clearing scan history..."
sqlite3 history.db "DELETE FROM scan_history;"
echo "✅"

# Step 5: Remove old TV mappings database and create fresh one
echo "🗑️  Removing old TradingView mappings..."
rm -f tv_mappings.db
echo "✅"

# Step 6: Clear chart debug folder
echo "🗑️  Clearing chart debug folder..."
rm -rf chart_debug/
mkdir chart_debug
echo "✅"

# Step 7: Run the mapping update to create fresh database
echo -e "\n🔄 Running TradingView mapping update..."
python3 update_mappings.py
echo "✅"

# Step 8: Show current database state
echo -e "\n📊 Current database state:"
echo "----------------------------------------"
ACTIVE_COUNT=$(sqlite3 history.db "SELECT COUNT(*) FROM active_coins;")
HISTORY_COUNT=$(sqlite3 history.db "SELECT COUNT(*) FROM scan_history;")
TV_COUNT=$(sqlite3 tv_mappings.db "SELECT COUNT(*) FROM tv_mappings;" 2>/dev/null || echo "0")
echo "Active coins: $ACTIVE_COUNT"
echo "Scan history: $HISTORY_COUNT"
echo "TV mappings: $TV_COUNT"
echo "----------------------------------------"

# Step 9: Start the bot fresh
echo -e "\n🚀 Starting bot..."
python3 manage_bot.py start
sleep 3

# Step 10: Check bot status
echo -e "\n🤖 Bot status:"
python3 manage_bot.py status

# Step 11: Show recent bot logs
echo -e "\n📝 Recent bot logs:"
echo "----------------------------------------"
tail -5 bot_output.log 2>/dev/null || echo "No logs yet"
echo "----------------------------------------"

# Step 12: Run a scan
echo -e "\n📊 Running scan..."
python3 scheduler.py

echo -e "\n========================================="
echo "✅ COMPLETE!"
echo "========================================="
echo "📁 Check chart_debug/ for generated charts"
echo "📝 Monitor with: tail -f trend_scanner.log"
echo "📱 Watch Telegram for notifications"
echo "========================================="