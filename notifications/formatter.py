"""
Notification message formatting
"""

from datetime import datetime
from typing import Dict, List
from config.constants import EXCHANGE_EMOJIS

class MessageFormatter:
    """Format notification messages"""
    
    @staticmethod
    def get_timestamp() -> str:
        """Get formatted timestamp"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    @staticmethod
    def format_entry(coin: Dict, config: Dict) -> str:
        """Format entry notification - volumes only"""
        lines = []
        
        # Timestamp
        lines.append(f"📅 {MessageFormatter.get_timestamp()}")
        lines.append("")
        
        # Header
        lines.append(f"🟢 {coin['symbol']} ({coin['name']})")
        
        # CMC link
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        lines.append(f"🔗 {cmc_url}")
        
        # Exchange volumes only - no gains or trends
        lines.append(f"💰 Exchange Volumes:")
        
        for exchange in config['TARGET_EXCHANGES']:
            volume = coin.get('exchange_volumes', {}).get(exchange, "N/A")
            exchange_emoji = EXCHANGE_EMOJIS.get(exchange, "💱")
            
            if volume != "N/A" and volume != 0:
                if isinstance(volume, (int, float)):
                    lines.append(f"{exchange_emoji} {exchange.title()}: ${volume:,.0f}")
                else:
                    lines.append(f"{exchange_emoji} {exchange.title()}: {volume}")
            else:
                lines.append(f"{exchange_emoji} {exchange.title()}: No volume")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_exit(coin: Dict) -> str:
        """Format exit notification with CMC link"""
        lines = []
        
        # Timestamp
        lines.append(f"📅 {MessageFormatter.get_timestamp()}")
        lines.append("")
        
        # Header
        lines.append(f"🔴 {coin['symbol']} ({coin['name']})")
        
        # CMC link
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        lines.append(f"🔗 {cmc_url}")
        
        # Message
        lines.append(f"has left the qualified list")
        
        return "\n".join(lines)