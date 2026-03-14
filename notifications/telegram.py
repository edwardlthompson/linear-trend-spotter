"""Enhanced Telegram notification client with interactive features"""
import requests
import io
import json
from typing import Optional, Dict, List
from datetime import datetime
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
            result = response.json()
            
            if not result.get('ok'):
                self.logger.error(f"Telegram API error: {result.get('description')}")
                return None
            
            return result
        except Exception as e:
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
            result = response.json()
            
            if result.get('ok'):
                return result['result']['message_id']
            else:
                self.logger.error(f"Failed to send photo: {result.get('description')}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error sending photo: {e}")
            return None
    
    def _build_context_keyboard(self, coin: Dict) -> dict | None:
        symbol = str(coin.get('symbol', ''))
        tv_url = f"https://www.tradingview.com/chart/?symbol={symbol}USD" # Generic URL, could be improved
        cg_url = str(
            coin.get('source_url')
            or coin.get('cmc_url')
            or MessageFormatter._build_coingecko_url(coin)
        ).strip()
        
        buttons = []
        if symbol:
            buttons.append({"text": "📈 View Chart", "url": tv_url})
        if cg_url:
            buttons.append({"text": "🔍 Analyze Coin", "url": cg_url})
            
        if buttons:
            return {"inline_keyboard": [buttons]}
        return None

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
        source_url = str(
            coin.get('source_url')
            or coin.get('cmc_url')
            or MessageFormatter._build_coingecko_url(coin)
        ).strip()
        message = f"🔴 <a href='{source_url}'>{coin['symbol']} ({coin['name']})</a> has left the qualified list"
        markup = self._build_context_keyboard(coin)
        return self.send_message(message, reply_markup=markup)