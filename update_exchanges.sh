#!/bin/bash
# Script to update exchange listings database
# Run this weekly via cron

cd /home/edwardlthompson/mysite

echo "========================================="
echo "🔄 Updating Exchange Listings Database"
echo "========================================="
echo "Started: $(date)"

# Run the update script
python3 exchange_data/update_exchanges.py >> exchange_update.log 2>&1

echo "Completed: $(date)"
echo "========================================="
