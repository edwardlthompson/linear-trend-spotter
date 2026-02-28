#!/usr/bin/env python3
"""
Telegram Bot Handler - Processes commands only (no buttons)
Run this as a separate process
"""

import os
import sys
import json
import logging
import time
import requests
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from database.models import ActiveCoinsDatabase
from database.cache import GeckoCache
from notifications.telegram import TelegramClient
from utils.logger import setup_logger

class TelegramBotHandler:
    """Handles Telegram bot commands"""
    
    def __init__(self):
        self.logger = setup_logger('telegram_bot')
        
        # Initialize database connections
        self.active_db = ActiveCoinsDatabase(settings.db_paths['history'])
        self.cache = GeckoCache(settings.db_paths['history'])
        
        # Initialize Telegram client
        if settings.telegram:
            self.telegram = TelegramClient(
                settings.telegram['bot_token'],
                settings.telegram['chat_id']
            )
        else:
            self.logger.error("Telegram not configured")
            sys.exit(1)
        
        # Polling interval (seconds)
        self.poll_interval = 2
        
        self.logger.info("Telegram Bot Handler initialized")
    
    def get_updates(self, offset: int = None) -> list:
        """Get updates from Telegram"""
        url = f"https://api.telegram.org/bot{settings.telegram['bot_token']}/getUpdates"
        params = {'timeout': 30}
        if offset:
            params['offset'] = offset
        
        try:
            response = requests.get(url, params=params, timeout=35)
            data = response.json()
            if data.get('ok'):
                return data.get('result', [])
            else:
                self.logger.error(f"Telegram API error: {data.get('description')}")
        except Exception as e:
            self.logger.error(f"Error getting updates: {e}")
        
        return []
    
    def run_polling(self):
        """Run polling loop to handle commands"""
        self.logger.info("Starting Telegram bot polling...")
        last_update_id = 0
        
        while True:
            try:
                updates = self.get_updates(last_update_id + 1)
                
                for update in updates:
                    update_id = update['update_id']
                    last_update_id = update_id
                    
                    # Handle commands
                    if 'message' in update and 'text' in update['message']:
                        text = update['message']['text']
                        
                        if text == '/start':
                            welcome = (
                                "🤖 Welcome to Linear Trend Spotter Bot!\n\n"
                                "Commands:\n"
                                "/status - Show current qualified coins\n"
                                "/list - List all tracked coins\n"
                                "/help - Show this help"
                            )
                            self.telegram.send_message(welcome)
                        
                        elif text == '/status':
                            active = self.active_db.get_active()
                            active_list = list(active.values())
                            
                            self.logger.info(f"Status command: found {len(active_list)} active coins")
                            self.telegram.send_status_update(active_list)
                        
                        elif text == '/list':
                            active = self.active_db.get_active()
                            if active:
                                coins = "\n".join([f"• {c['symbol']} - {c['name']}" for c in active.values()])
                                self.telegram.send_message(f"📋 Tracked coins:\n{coins}")
                            else:
                                self.telegram.send_message("📋 No coins currently tracked")
                        
                        elif text == '/help':
                            help_text = (
                                "🤖 <b>Linear Trend Spotter Commands:</b>\n\n"
                                "/start - Welcome message\n"
                                "/status - Show current qualified coins\n"
                                "/list - List all tracked coins\n"
                                "/help - Show this help"
                            )
                            self.telegram.send_message(help_text)
                
                time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Stopping bot...")
                break
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
                time.sleep(10)

def main():
    handler = TelegramBotHandler()
    handler.run_polling()

if __name__ == "__main__":
    main()