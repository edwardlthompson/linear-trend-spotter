"""Enhanced Telegram notification client with interactive features"""
import html
import io
import json
import requests
from typing import Optional, Dict
import logging
from notifications.formatter import MessageFormatter

class TelegramClient:
    """Send notifications via Telegram with interactive features"""
    
    API_URL = "https://api.telegram.org/bot{token}/"
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = self.API_URL.format(token=bot_token)
        self.session = requests.Session()
        self.logger = logging.getLogger('Telegram')
    
    def _request(self, method: str, data: dict) -> Optional[dict]:
        """Make a request to Telegram API"""
        try:
            url = f"{self.base_url}{method}"
            
            if 'reply_markup' in data and isinstance(data['reply_markup'], dict):
                data['reply_markup'] = json.dumps(data['reply_markup'])
            
            response = self.session.post(url, data=data, timeout=10)
            response.raise_for_status()
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"Telegram invalid JSON for {method}: {e}")
                return None

            if not result.get('ok'):
                self.logger.error(f"Telegram API error: {result.get('description')}")
                return None

            return result
        except requests.RequestException as e:
            self.logger.error(f"Telegram request error: {e}")
            return None
    
    def send_message(self, text: str, parse_mode: str = 'HTML', reply_markup: dict = None) -> Optional[int]:
        """Send a text message"""
        data = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup:
            data['reply_markup'] = reply_markup
        
        result = self._request('sendMessage', data)
        if result and result.get('ok'):
            return result['result']['message_id']
        return None
    
    def edit_message_text(self, message_id: int, text: str, parse_mode: str = 'HTML', reply_markup: dict = None) -> bool:
        """Edit an existing message"""
        data = {
            'chat_id': self.chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup:
            data['reply_markup'] = reply_markup
            
        result = self._request('editMessageText', data)
        return bool(result and result.get('ok'))

    def answer_callback_query(self, callback_query_id: str, text: str = None) -> bool:
        """Acknowledge callback query"""
        data = {'callback_query_id': callback_query_id}
        if text:
            data['text'] = text
        result = self._request('answerCallbackQuery', data)
        return bool(result and result.get('ok'))
    
    def send_photo(self, photo: io.BytesIO, caption: str = None, reply_markup: dict = None) -> Optional[int]:
        """Send a photo with caption"""
        try:
            url = f"{self.base_url}sendPhoto"
            files = {'photo': ('chart.png', photo, 'image/png')}
            data = {'chat_id': self.chat_id}
            
            if caption:
                data['caption'] = caption
                data['parse_mode'] = 'HTML'
                
            if reply_markup:
                data['reply_markup'] = json.dumps(reply_markup)
            
            response = self.session.post(url, data=data, files=files, timeout=30)
            response.raise_for_status()
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"Telegram sendPhoto invalid JSON: {e}")
                return None

            if result.get('ok'):
                return result['result']['message_id']
            self.logger.error(f"Failed to send photo: {result.get('description')}")
            return None

        except requests.RequestException as e:
            self.logger.error(f"Error sending photo: {e}")
            return None
    
    def _build_context_keyboard(self, coin: Dict) -> dict | None:
        symbol = str(coin.get('symbol', ''))
        tv_url = f"https://www.tradingview.com/chart/?symbol={symbol}USD" # Generic URL, could be improved
        analyze_url = MessageFormatter.primary_market_url(coin).strip()

        rows: list[list[dict]] = []
        row0: list[dict] = []
        if symbol:
            row0.append({"text": "📈 View Chart", "url": tv_url})
        if analyze_url:
            row0.append({"text": "🔍 Analyze Coin", "url": analyze_url})
        if row0:
            rows.append(row0)

        ex_row: list[dict] = []
        for label, url in MessageFormatter.exchange_url_buttons(coin):
            if not url:
                continue
            ex_row.append({"text": label, "url": url})
            if len(ex_row) >= 3:
                rows.append(ex_row)
                ex_row = []
        if ex_row:
            rows.append(ex_row)

        if rows:
            return {"inline_keyboard": rows}
        return None

    def coin_link_reply_markup(self, coin: Dict) -> dict | None:
        """Inline keyboard for entry/exit messages (chart, CMC/CG, per-exchange links)."""
        return self._build_context_keyboard(coin)

    def send_entry_notification(self, coin: Dict, chart_bytes: bytes = None) -> Optional[int]:
        """Send entry notification with chart and backtest details"""
        caption = MessageFormatter.format_entry(coin)
        markup = self._build_context_keyboard(coin)
        
        # Send with chart if available
        if chart_bytes:
            img_data = io.BytesIO(chart_bytes)
            return self.send_photo(img_data, caption=caption, reply_markup=markup)
        else:
            return self.send_message(caption, reply_markup=markup)
    
    def send_exit_notification(self, coin: Dict) -> Optional[int]:
        """Send exit notification without timestamp"""
        header_url = MessageFormatter.primary_market_url(coin).strip()
        sym = html.escape(str(coin.get('symbol', '')), quote=False)
        nm = html.escape(str(coin.get('name', '')), quote=False)
        href = html.escape(header_url, quote=True)
        message = f"🔴 <a href='{href}'>{sym} ({nm})</a> has left the qualified list"
        markup = self._build_context_keyboard(coin)
        return self.send_message(message, reply_markup=markup)