#!/usr/bin/env python3
"""
Telegram Bot Handler - Processes commands only (no buttons)
Run this as a separate process
"""

import os
import sys
import json
import html
import time
import requests
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
        self.bot_mode = settings.telegram_bot_mode
        
        self.logger.info("Telegram Bot Handler initialized")

    def _load_metrics_history_tail(self, n: int = 1) -> list:
        path = settings.metrics_file
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list) or not data:
                return []
            return data[-n:]
        except Exception as exc:
            self.logger.error("Error reading metrics.json: %s", exc)
            return []

    def _diag_health_text(self) -> str:
        hb_path = settings.DATA_DIR / settings.scan_heartbeat_file
        hb_line = "Heartbeat: <i>not found</i>"
        if hb_path.exists():
            try:
                hb = json.loads(hb_path.read_text(encoding="utf-8"))
                if isinstance(hb, dict):
                    hb_line = (
                        f"Heartbeat: <b>{html.escape(str(hb.get('status', '')), quote=False)}</b> "
                        f"finished <code>{html.escape(str(hb.get('finished_at', '')), quote=False)}</code>"
                    )
            except Exception as exc:
                hb_line = f"Heartbeat: <i>read error ({html.escape(str(exc), quote=False)})</i>"
        last = self._load_metrics_history_tail(1)
        coins = "n/a"
        if last and isinstance(last[0], dict):
            coins = str(last[0].get("coins_processed", "n/a"))
        return (
            "<b>/health</b>\n"
            f"{hb_line}\n"
            f"Last metrics run coins_processed: <b>{html.escape(coins, quote=False)}</b>"
        )

    def _diag_last_text(self) -> str:
        last = self._load_metrics_history_tail(1)
        if not last:
            return "<b>/last</b>\nNo <code>metrics.json</code> history yet."
        row = last[0]
        stamp = row.get("timestamp") if isinstance(row.get("timestamp"), str) else "unknown"
        dur = row.get("duration", "?")
        return (
            "<b>/last</b>\n"
            f"Last metrics row timestamp: <code>{html.escape(str(stamp), quote=False)}</code>\n"
            f"Duration (s): <code>{html.escape(str(dur), quote=False)}</code>"
        )

    def _diag_cost_text(self) -> str:
        last = self._load_metrics_history_tail(1)
        if not last:
            return "<b>/cost</b>\nNo metrics history."
        counts = last[0].get("counts") if isinstance(last[0], dict) else {}
        if not isinstance(counts, dict):
            counts = {}
        cg = {k: v for k, v in counts.items() if str(k).startswith("coingecko_http_")}
        lines = [f"• <code>{html.escape(str(k), quote=False)}</code>: {v}" for k, v in sorted(cg.items())[:14]]
        poly = counts.get("polygon_http_total", 0)
        cmc = counts.get("cmc_http_total", 0)
        extra = f"\nPolygon HTTP total: <b>{poly}</b>\nCMC HTTP total: <b>{cmc}</b>"
        body = "\n".join(lines) if lines else "<i>No CoinGecko HTTP counters in last row.</i>"
        scan_costs_path = settings.DATA_DIR / settings.scan_costs_file
        sc_note = ""
        if scan_costs_path.exists():
            sc_note = f"\n<code>{html.escape(scan_costs_path.name, quote=False)}</code> present on disk."
        return "<b>/cost</b> (last metrics row)\n" + body + extra + sc_note
    
    def get_updates(self, offset: int = None) -> list:
        """Get updates from Telegram"""
        url = f"https://api.telegram.org/bot{settings.telegram['bot_token']}/getUpdates"
        params = {'timeout': 30}
        if offset:
            params['offset'] = offset
        
        try:
            response = requests.get(url, params=params, timeout=35)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Error getting updates (HTTP): {e}")
            return []

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            self.logger.error(f"Error getting updates (invalid JSON): {e}")
            return []

        if data.get('ok'):
            return data.get('result', [])
        self.logger.error(f"Telegram API error: {data.get('description')}")
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
            f"<b>Last scan:</b> {html.escape(str(scan_time), quote=False)}\n"
            f"<b>Duration:</b> {html.escape(str(scan_duration), quote=False)}"
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
            f"• <b>{html.escape(str(c.get('symbol', '')), quote=False)}</b> - "
            f"{html.escape(str(c.get('name', '')), quote=False)} "
            f"<i>(Score: {c.get('uniformity_score', 0):.0f})</i>"
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

    def _set_webhook(self) -> None:
        if not settings.telegram_webhook_url:
            raise RuntimeError("TELEGRAM_WEBHOOK_URL is required when TELEGRAM_BOT_MODE=webhook")
        url = f"https://api.telegram.org/bot{settings.telegram['bot_token']}/setWebhook"
        params = {
            "url": settings.telegram_webhook_url.rstrip("/") + settings.telegram_webhook_path,
        }
        if settings.telegram_webhook_secret_token:
            params["secret_token"] = settings.telegram_webhook_secret_token
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("ok"):
            raise RuntimeError(f"setWebhook failed: {payload.get('description')}")

    def _clear_webhook(self) -> None:
        url = f"https://api.telegram.org/bot{settings.telegram['bot_token']}/deleteWebhook"
        try:
            requests.get(url, params={"drop_pending_updates": "false"}, timeout=20)
        except Exception:
            pass

    def _process_message(self, message: dict) -> None:
        chat_id = message.get('chat', {}).get('id')

        # Security check: verify sender
        if str(chat_id) != str(settings.telegram['chat_id']):
            self.logger.warning(f"Ignored message from unauthorized chat: {chat_id}")
            return

        text_raw = message.get('text', '')
        cmd = text_raw.strip().split()[0].split("@", 1)[0].lower() if text_raw.strip() else ''

        if cmd == '/start':
            welcome = (
                "🤖 <b>Welcome to Linear Trend Spotter Bot!</b>\n\n"
                "Use the interactive buttons below to navigate."
            )
            self.telegram.send_message(welcome, reply_markup=self._get_main_keyboard())

        elif cmd == '/status':
            status_msg = self._get_status_text()
            markup = {"inline_keyboard": [[{"text": "🔄 Refresh", "callback_data": "status"}]]}
            self.telegram.send_message(status_msg, reply_markup=markup)

        elif cmd == '/list':
            msg_text, markup = self._get_list_text_markup(0)
            self.telegram.send_message(msg_text, reply_markup=markup)

        elif settings.scanner_diag_commands_enabled and cmd in ('/health', '/last', '/cost'):
            if cmd == '/health':
                self.telegram.send_message(self._diag_health_text())
            elif cmd == '/last':
                self.telegram.send_message(self._diag_last_text())
            else:
                self.telegram.send_message(self._diag_cost_text())

        elif cmd == '/help':
            help_lines = [
                "🤖 <b>Linear Trend Spotter Commands:</b>\n",
                "/start - Welcome interactive menu",
                "/status - Show current qualified coins",
                "/list - List all tracked coins",
                "/help - Show this help",
            ]
            if settings.scanner_diag_commands_enabled:
                help_lines.extend(
                    [
                        "/health - Heartbeat + last metrics coins_processed",
                        "/last - Last metrics.json row summary",
                        "/cost - CoinGecko HTTP counters from last metrics row",
                    ]
                )
            self.telegram.send_message("\n".join(help_lines))

    def _process_callback_query(self, query: dict) -> None:
        chat_id = query.get('message', {}).get('chat', {}).get('id')
        if str(chat_id) != str(settings.telegram['chat_id']):
            self.logger.warning(f"Ignored callback from unauthorized chat: {chat_id}")
            return

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

    def process_update(self, update: dict) -> None:
        if 'message' in update and 'text' in update['message']:
            self._process_message(update['message'])
        elif 'callback_query' in update:
            self._process_callback_query(update['callback_query'])
    
    def run_polling(self):
        """Run polling loop to handle commands"""
        self.logger.info("Starting Telegram bot polling...")
        self._clear_webhook()
        last_update_id = 0
        
        while True:
            try:
                updates = self.get_updates(last_update_id + 1)
                
                for update in updates:
                    update_id = update['update_id']
                    last_update_id = update_id
                    self.process_update(update)
                
                time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Stopping bot...")
                break
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
                time.sleep(10)

    def run_webhook(self):
        """Run webhook mode (optional)."""
        self._set_webhook()
        self.logger.info(
            "Starting Telegram webhook server on 0.0.0.0:%s%s",
            settings.telegram_webhook_port,
            settings.telegram_webhook_path,
        )

        parent = self
        expected_path = settings.telegram_webhook_path
        expected_secret = settings.telegram_webhook_secret_token

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path == "/health":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self):  # noqa: N802
                if self.path != expected_path:
                    self.send_response(404)
                    self.end_headers()
                    return
                if expected_secret:
                    got = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                    if got != expected_secret:
                        self.send_response(403)
                        self.end_headers()
                        return
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    update = json.loads(raw.decode("utf-8"))
                    if isinstance(update, dict):
                        parent.process_update(update)
                except Exception as exc:
                    parent.logger.error("Webhook update parse/process error: %s", exc)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("0.0.0.0", settings.telegram_webhook_port), Handler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            self.logger.info("Stopping webhook server...")
        finally:
            server.server_close()

def main():
    handler = TelegramBotHandler()
    if handler.bot_mode == "webhook":
        handler.run_webhook()
    else:
        handler.run_polling()

if __name__ == "__main__":
    main()