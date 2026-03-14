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
from database.cache import PriceCache
from notifications.telegram import TelegramClient
from utils.logger import setup_logger

class TelegramBotHandler:
    """Handles Telegram bot commands"""
    
    def __init__(self):
        self.logger = setup_logger('telegram_bot')
        
        # Initialize database connections
        self.active_db = ActiveCoinsDatabase(settings.db_paths['scanner'])
        self.cache = PriceCache(settings.db_paths['scanner'])
        
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
    
    def _get_status_text(self) -> str:
        active = self.active_db.get_active()
        active_list = list(active.values())
        
        scan_time = "Unknown"
        scan_duration = "Unknown"
        try:
            scan_stats_path = Path('scan_stats.json')
            if scan_stats_path.exists():
                with open(scan_stats_path, 'r') as f:
                    stats = json.load(f)
                    if stats:
                        last_scan = stats[-1]  # Most recent
                        scan_time = last_scan.get('last_run', 'Unknown')
                        scan_duration = f"{last_scan.get('duration', 0):.1f}s"
        except Exception as e:
            self.logger.error(f"Error reading scan stats: {e}")
        
        return (
            f"📊 <b>Status Report</b>\n\n"
            f"<b>Active coins:</b> {len(active_list)}\n"
            f"<b>Last scan:</b> {scan_time}\n"
            f"<b>Duration:</b> {scan_duration}"
        )

    def _get_list_text_markup(self, page: int = 0) -> tuple[str, dict]:
        active = self.active_db.get_active()
        if not active:
            return "📋 No coins currently tracked", None
        
        coins = list(active.values())
        per_page = 10
        total_pages = max(1, (len(coins) - 1) // per_page + 1)
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * per_page
        end_idx = start_idx + per_page
        page_coins = coins[start_idx:end_idx]
        
        text = f"📋 <b>Tracked coins (Page {page+1}/{total_pages})</b>\n\n"
        lines = [
            f"• <b>{c['symbol']}</b> - {c['name']} <i>(Score: {c.get('uniformity_score', 0):.0f})</i>"
            for c in page_coins
        ]
        text += "\n".join(lines)
        
        buttons = []
        if page > 0:
            buttons.append({"text": "⬅️ Prev", "callback_data": f"list_{page-1}"})
        if page < total_pages - 1:
            buttons.append({"text": "Next ➡️", "callback_data": f"list_{page+1}"})
        
        markup = {"inline_keyboard": [buttons]} if buttons else None
        return text, markup

    def _get_main_keyboard(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "📊 Status Report", "callback_data": "status"},
                    {"text": "📋 Tracked Coins", "callback_data": "list_0"}
                ]
            ]
        }
    
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
                    
                    if 'message' in update and 'text' in update['message']:
                        text = update['message']['text']
                        
                        if text == '/start':
                            welcome = (
                                "🤖 <b>Welcome to Linear Trend Spotter Bot!</b>\n\n"
                                "Use the interactive buttons below to navigate."
                            )
                            self.telegram.send_message(welcome, reply_markup=self._get_main_keyboard())
                        
                        elif text == '/status':
                            status_msg = self._get_status_text()
                            markup = {"inline_keyboard": [[{"text": "🔄 Refresh", "callback_data": "status"}]]}
                            self.telegram.send_message(status_msg, reply_markup=markup)
                        
                        elif text == '/list':
                            msg_text, markup = self._get_list_text_markup(0)
                            self.telegram.send_message(msg_text, reply_markup=markup)
                        
                        elif text == '/help':
                            help_text = (
                                "🤖 <b>Linear Trend Spotter Commands:</b>\n\n"
                                "/start - Welcome interactive menu\n"
                                "/status - Show current qualified coins\n"
                                "/list - List all tracked coins\n"
                                "/help - Show this help"
                            )
                            self.telegram.send_message(help_text)
                    
                    elif 'callback_query' in update:
                        query = update['callback_query']
                        cb_id = query['id']
                        cb_data = query.get('data', '')
                        msg_id = query.get('message', {}).get('message_id')
                        
                        if cb_data == 'status':
                            status_msg = self._get_status_text()
                            markup = {"inline_keyboard": [[{"text": "🔄 Refresh", "callback_data": "status"}]]}
                            self.telegram.edit_message_text(msg_id, status_msg, reply_markup=markup)
                            self.telegram.answer_callback_query(cb_id, text="Status Refreshed!")
                            
                        elif cb_data.startswith('list_'):
                            page = int(cb_data.split('_')[1])
                            msg_text, markup = self._get_list_text_markup(page)
                            self.telegram.edit_message_text(msg_id, msg_text, reply_markup=markup)
                            self.telegram.answer_callback_query(cb_id)
                
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