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
    
    def send_message(self, text: str, parse_mode: str = 'HTML') -> Optional[int]:
        """Send a text message"""
        data = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        result = self._request('sendMessage', data)
        if result and result.get('ok'):
            return result['result']['message_id']
        return None
    
    def send_photo(self, photo: io.BytesIO, caption: str = None) -> Optional[int]:
        """Send a photo with caption"""
        try:
            url = f"{self.base_url}sendPhoto"
            files = {'photo': ('chart.png', photo, 'image/png')}
            data = {'chat_id': self.chat_id}
            
            if caption:
                data['caption'] = caption
                data['parse_mode'] = 'HTML'
            
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
    
    def send_entry_notification(self, coin: Dict, chart_bytes: bytes = None) -> Optional[int]:
        """Send entry notification with chart and backtest details"""
        caption = MessageFormatter.format_entry(coin)
        
        # Send with chart if available
        if chart_bytes:
            img_data = io.BytesIO(chart_bytes)
            return self.send_photo(img_data, caption=caption)
        else:
            return self.send_message(caption)
    
    def send_exit_notification(self, coin: Dict) -> Optional[int]:
        """Send exit notification without timestamp"""
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        message = f"🔴 <a href='{cmc_url}'>{coin['symbol']} ({coin['name']})</a> has left the qualified list"
        return self.send_message(message)