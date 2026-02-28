"""
Chart generator using QuickChart.io API
Creates 30-day cumulative percentage change charts with green fill
"""

import requests
import json
import urllib.parse
import time
from typing import Optional
import logging
from datetime import datetime, timedelta
import os

class ChartGenerator:
    """Generate price charts using QuickChart.io"""
    
    def __init__(self):
        self.logger = logging.getLogger('ChartGenerator')
        self.quickchart_url = "https://quickchart.io/chart"
        # Create a directory for saving charts temporarily (for debugging)
        self.debug_dir = os.path.join(os.path.dirname(__file__), 'chart_debug')
        os.makedirs(self.debug_dir, exist_ok=True)
    
    def fetch_price_data(self, gecko_id: str) -> Optional[list]:
        """Fetch 30-day price data from CoinGecko"""
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': '30',
                'interval': 'daily'
            }
            
            self.logger.info(f"📡 Fetching price data for {gecko_id}")
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                prices = [point[1] for point in data.get('prices', [])]
                self.logger.info(f"✅ Got {len(prices)} price points for {gecko_id}")
                
                # Debug: save prices to file
                debug_file = os.path.join(self.debug_dir, f"{gecko_id}_prices.json")
                with open(debug_file, 'w') as f:
                    json.dump(prices, f)
                
                return prices
            elif response.status_code == 429:
                self.logger.error(f"❌ Rate limited (429) for {gecko_id}")
                return None
            else:
                self.logger.error(f"❌ Failed to fetch price data: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error fetching price data: {e}")
            return None
    
    def calculate_cumulative_percentage(self, prices: list) -> list:
        """
        Calculate cumulative percentage change from day 0
        First value is 0%, last value is total % change over 30 days
        """
        if not prices or len(prices) < 2:
            return []
        
        base_price = prices[0]  # Price at day 0 (oldest)
        cumulative = []
        
        for price in prices:
            pct_change = ((price - base_price) / base_price) * 100
            cumulative.append(round(pct_change, 2))
        
        return cumulative
    
    def generate_chart_url(self, gecko_id: str, symbol: str, width: int = 500, height: int = 300) -> Optional[str]:
        """Generate a QuickChart.io URL for the cumulative percentage chart"""
        
        prices = self.fetch_price_data(gecko_id)
        if not prices or len(prices) < 2:
            self.logger.error(f"❌ Insufficient price data for {symbol}")
            return None
        
        # Calculate cumulative percentage changes (starts at 0)
        cumulative = self.calculate_cumulative_percentage(prices)
        
        # Use ALL 30 data points - no downsampling
        display_data = cumulative
        
        # No x-axis labels - just empty strings
        empty_labels = [''] * len(display_data)
        
        # Calculate y-axis range with padding
        max_val = max(cumulative)
        min_val = min(cumulative)
        padding = max(abs(max_val), abs(min_val)) * 0.1
        if padding == 0:
            padding = 5
        
        # Final value for title
        final_value = cumulative[-1]
        
        # Working configuration based on successful tests
        chart_config = {
            "type": "line",
            "data": {
                "labels": empty_labels,
                "datasets": [{
                    "data": display_data,
                    "borderColor": "#22c55e",  # Green line
                    "backgroundColor": "rgba(34, 197, 94, 0.15)",  # Light green fill
                    "borderWidth": 2,
                    "pointRadius": 0,  # No points
                    "fill": True
                }]
            },
            "options": {
                "title": {
                    "display": True,
                    "text": f"{symbol}: {final_value:+.1f}%",
                    "fontSize": 14
                },
                "legend": {
                    "display": False
                },
                "scales": {
                    "yAxes": [{
                        "ticks": {
                            "min": round(min_val - padding, 1),
                            "max": round(max_val + padding, 1),
                            "stepSize": 10,
                            "callback": "function(value) { return value + '%'; }"
                        },
                        "gridLines": {
                            "color": "#e5e7eb",
                            "zeroLineColor": "#000000",
                            "zeroLineWidth": 2
                        }
                    }],
                    "xAxes": [{
                        "gridLines": {
                            "display": False
                        },
                        "ticks": {
                            "display": False
                        }
                    }]
                },
                "tooltips": {
                    "enabled": False
                }
            }
        }
        
        # Convert to JSON string
        chart_json = json.dumps(chart_config)
        
        # Create QuickChart URL
        encoded_chart = urllib.parse.quote(chart_json)
        
        chart_url = f"{self.quickchart_url}?c={encoded_chart}&width={width}&height={height}&format=png"
        self.logger.info(f"✅ Generated chart URL for {symbol}")
        
        # Debug: save URL to file
        debug_file = os.path.join(self.debug_dir, f"{symbol}_url.txt")
        with open(debug_file, 'w') as f:
            f.write(chart_url)
        
        return chart_url
    
    def get_chart_image(self, gecko_id: str, symbol: str) -> Optional[bytes]:
        """Get chart image bytes directly"""
        self.logger.info(f"🎨 Generating chart for {symbol}...")
        
        # Add a small delay before fetching to help with rate limits
        time.sleep(1)
        
        chart_url = self.generate_chart_url(gecko_id, symbol)
        if not chart_url:
            self.logger.error(f"❌ No chart URL for {symbol}")
            return None
        
        try:
            self.logger.info(f"📥 Downloading chart from QuickChart.io...")
            
            response = requests.get(chart_url, timeout=30)
            
            self.logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                content_length = len(response.content)
                self.logger.info(f"✅ Downloaded chart image for {symbol}: {content_length} bytes")
                
                # Debug: save image to file
                debug_file = os.path.join(self.debug_dir, f"{symbol}_chart.png")
                with open(debug_file, 'wb') as f:
                    f.write(response.content)
                self.logger.info(f"💾 Saved chart to {debug_file}")
                
                return response.content
            else:
                self.logger.error(f"❌ Failed to download chart: HTTP {response.status_code}")
                self.logger.error(f"Response text: {response.text[:200]}")
                
                # Try to save error response for debugging
                debug_file = os.path.join(self.debug_dir, f"{symbol}_error.html")
                with open(debug_file, 'wb') as f:
                    f.write(response.content)
                self.logger.info(f"💾 Saved error response to {debug_file}")
                
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error downloading chart: {e}", exc_info=True)
            return None