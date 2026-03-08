"""
Notification message formatting
"""

from datetime import datetime
from typing import Dict, List
from config.constants import EXCHANGE_EMOJIS

class MessageFormatter:
    """Format notification messages per spec §10.1-10.2"""
    
    @staticmethod
    def format_entry(coin: Dict) -> str:
        """
        Format entry notification per spec §10.1
        Returns HTML-formatted caption for Telegram photo
        """
        # Build CMC URL
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        
        # Get data
        symbol = coin['symbol']
        name = coin['name']
        gain_7d = coin['gains'].get('7d', 0)
        gain_30d = coin['gains'].get('30d', 0)
        score = coin.get('uniformity_score', 0)
        
        # Header with HTML link
        caption = f"🟢 <a href='{cmc_url}'>{symbol} ({name})</a>\n\n"
        
        # Gains section
        caption += f"📊 Gains:\n"
        caption += f"   7d: +{gain_7d:.1f}%\n"
        caption += f"   30d: +{gain_30d:.1f}%\n\n"
        
        # Uniformity score
        caption += f"📈 Uniformity Score: {score:.0f}/100\n\n"
        
        # Exchange volumes
        caption += f"💰 Exchange Volumes:\n"
        
        volumes = coin.get('exchange_volumes', {})
        listed_on = coin.get('listed_on', ['coinbase', 'kraken', 'mexc'])
        
        for exchange in listed_on:
            volume = volumes.get(exchange, "N/A")
            exchange_emoji = EXCHANGE_EMOJIS.get(exchange, "💱")
            
            # Show "No volume" instead of $0 or N/A per spec §10.1
            if volume == "N/A" or volume == 0 or volume == "0":
                caption += f"{exchange_emoji} {exchange.title()}: No volume\n"
            elif isinstance(volume, (int, float)):
                caption += f"{exchange_emoji} {exchange.title()}: ${volume:,.0f}\n"
            else:
                caption += f"{exchange_emoji} {exchange.title()}: {volume}\n"
        
        return caption
    
    @staticmethod
    def format_exit(coin: Dict) -> str:
        """
        Format exit notification per spec §10.2
        Returns plain text message
        """
        symbol = coin['symbol']
        name = coin['name']
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        
        message = f"🔴 {symbol} ({name})\n"
        message += f"🔗 {cmc_url}\n"
        message += f"has left the qualified list"
        
        return message