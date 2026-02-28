"""Gain calculation and filtering with 7d and 30d requirements"""
from typing import Dict, Tuple, Optional, List
from config.constants import STABLECOINS

class GainFilter:
    """Process gain requirements"""
    
    @staticmethod
    def check_volume(coin_data: Dict, min_volume: int) -> bool:
        """Check if coin meets minimum volume requirement"""
        try:
            volume_24h = coin_data.get('volume_24h', 0)
            return volume_24h >= min_volume
        except Exception as e:
            return False
    
    @staticmethod
    def check_gain_requirements(gains: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Check if gains meet the >1% per day requirement for 7d and 30d
        """
        try:
            # Get the gain values
            gain_7d = gains.get('7d', 0)
            gain_30d = gains.get('30d', 0)
            
            # Skip if we don't have the basic data
            if gain_7d == 0 or gain_30d == 0:
                return False, None
            
            # Check >1% per day requirement
            # 7d > 7%, 30d > 30%
            if (gain_7d > 7 and gain_30d > 30):
                return True, {
                    '7d': gain_7d,
                    '30d': gain_30d,
                }
            
        except Exception as e:
            print(f"Error checking gains: {e}")
        
        return False, None
    
    @staticmethod
    def calculate_gains_from_prices(prices: List[float]) -> Optional[Dict]:
        """
        Calculate gain percentages from price history
        Used to get accurate 30d gains
        """
        if len(prices) < 30:
            return None
        
        base_price = prices[0]
        
        gains = {}
        
        # 7-day gain (day 7)
        if len(prices) >= 7:
            gain_7d = ((prices[6] - base_price) / base_price) * 100
            gains['7d'] = round(gain_7d, 2)
        else:
            gains['7d'] = 0
        
        # 30-day gain (day 30)
        if len(prices) >= 30:
            gain_30d = ((prices[29] - base_price) / base_price) * 100
            gains['30d'] = round(gain_30d, 2)
        else:
            gains['30d'] = 0
        
        return gains