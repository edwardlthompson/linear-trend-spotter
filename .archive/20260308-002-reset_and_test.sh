#!/bin/bash
# Reset all qualified coins and restart bot for fresh testing

echo "========================================="
echo "🔄 RESETTING QUALIFIED COINS AND BOT"
echo "========================================="

cd /home/edwardlthompson/mysite

# Step 1: Stop the bot
echo -n "🛑 Stopping bot... "
python3 manage_bot.py stop
sleep 2

# Step 2: Kill any remaining processes
echo -n "🔪 Killing any remaining processes... "
pkill -f "python3 telegram_bot.py" 2>/dev/null
pkill -f "manage_bot.py" 2>/dev/null
rm -f bot.pid
echo "✅"

# Step 3: Clear the active coins table
echo -n "🗑️  Clearing active coins from database... "
sqlite3 history.db "DELETE FROM active_coins;"
echo "✅"

# Step 4: Clear the scan history (optional - comment out if you want to keep history)
echo -n "🗑️  Clearing scan history (optional)... "
sqlite3 history.db "DELETE FROM scan_history;"
echo "✅"

# Step 5: Show current database state
echo -e "\n📊 Current database state:"
echo "----------------------------------------"
ACTIVE_COUNT=$(sqlite3 history.db "SELECT COUNT(*) FROM active_coins;")
HISTORY_COUNT=$(sqlite3 history.db "SELECT COUNT(*) FROM scan_history;")
echo "Active coins: $ACTIVE_COUNT"
echo "Scan history: $HISTORY_COUNT"
echo "----------------------------------------"

# Step 6: Start the bot fresh
echo -e "\n🚀 Starting bot..."
python3 manage_bot.py start
sleep 3

# Step 7: Check bot status
echo -e "\n🤖 Bot status:"
python3 manage_bot.py status

# Step 8: Show recent logs
echo -e "\n📝 Recent bot logs:"
echo "----------------------------------------"
tail -5 bot_output.log 2>/dev/null || echo "No logs yet"

# Step 9: Instructions
echo -e "\n========================================="
echo "✅ READY FOR TESTING!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Run a scan to generate new qualified coins:"
echo "   python3 scheduler.py"
echo ""
echo "2. Watch for notifications on Telegram"
echo ""
echo "3. Check bot logs if needed:"
echo "   tail -f bot_output.log"
echo ""
echo "4. Check status anytime:"
echo "   python3 manage_bot.py status"
echo "========================================="
