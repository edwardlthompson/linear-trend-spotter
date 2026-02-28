#!/bin/bash
# Script to update the mapping database automatically
# Can be set up as a cron job to run monthly

echo "🔄 Updating CoinGecko mapping database..."
cd "$(dirname "$0")"

# Run the mapping builder
python3 build_mapping_db.py

# Check if successful
if [ $? -eq 0 ]; then
    echo "✅ Mapping database updated successfully"
else
    echo "❌ Failed to update mapping database"
    exit 1
fi