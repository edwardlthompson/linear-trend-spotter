"""Enhanced Telegram notification client with interactive features"""
import requests
import io
import json
from typing import Optional, Dict, List
from datetime import datetime
import logging

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
        """Send entry notification with chart and exchange volumes"""
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        
        # Get gains
        gain_7d = coin['gains'].get('7d', 0)
        gain_14d = coin['gains'].get('14d', 0)
        gain_30d = coin['gains'].get('30d', 0)
        
        caption = (
            f"🟢 <a href='{cmc_url}'>{coin['symbol']} ({coin['name']})</a>\n\n"
            f"📊 Gains:\n"
            f"   7d: +{gain_7d:.1f}%\n"
            f"   14d: +{gain_14d:.1f}%\n"
            f"   30d: +{gain_30d:.1f}%\n\n"
            f"📈 Uniformity: {coin['uniformity_score']}/100\n\n"
            f"💰 Exchange Volumes:\n"
        )
        
        # Add exchange volumes
        for exchange in coin.get('listed_on', []):
            volume = coin.get('exchange_volumes', {}).get(exchange, "N/A")
            if exchange == 'coinbase':
                emoji = "🟦"
            elif exchange == 'kraken':
                emoji = "🐙"
            elif exchange == 'mexc':
                emoji = "🟪"
            else:
                emoji = "💱"
            
            if volume != "N/A" and volume != 0:
                if isinstance(volume, (int, float)):
                    caption += f"{emoji} {exchange.title()}: ${volume:,.0f}\n"
                else:
                    caption += f"{emoji} {exchange.title()}: {volume}\n"
            else:
                caption += f"{emoji} {exchange.title()}: No volume\n"
        
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