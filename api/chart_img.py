"""
Chart-IMG API client for TradingView charts
Handles proper exchange pair formatting and parallel requests
"""

import requests
import logging
import time
import concurrent.futures
from typing import Optional, Dict, List, Tuple
from threading import Lock

class ChartIMGClient:
    """Generate TradingView charts using Chart-IMG API"""
    
    BASE_URL_V2 = "https://api.chart-img.com/v2/tradingview/advanced-chart"
    
    # Exchange-specific pair formats [citation:1]
    EXCHANGE_FORMATS = {
        'coinbase': {
            'format': '{symbol}USD',
            'prefix': 'COINBASE',
            'quote': 'USD',
            'separator': ''  # COINBASE:BTCUSD
        },
        'kraken': {
            'format': '{symbol}USD',
            'prefix': 'KRAKEN',
            'quote': 'USD',
            'separator': '',  # KRAKEN:XBTUSD (special case for BTC)
            'special': {'BTC': 'XBTUSD'}  # Kraken uses XBT for Bitcoin
        },
        'binance': {
            'format': '{symbol}USDT',
            'prefix': 'BINANCE',
            'quote': 'USDT',
            'separator': ''  # BINANCE:BTCUSDT
        },
        'mexc': {
            'format': '{symbol}USDT',
            'prefix': 'MEXC',
            'quote': 'USDT',
            'separator': ''  # MEXC:BTCUSDT
        },
        'bybit': {
            'format': '{symbol}USDT',
            'prefix': 'BYBIT',
            'quote': 'USDT',
            'separator': ''  # BYBIT:BTCUSDT
        },
        'okx': {
            'format': '{symbol}-{quote}',
            'prefix': 'OKX',
            'quote': 'USDT',
            'separator': '-',  # OKX:BTC-USDT
            'quote_override': {'USD': 'USDT'}  # OKX uses USDT for most pairs
        }
    }
    
    # Default to USDT for exchanges that prefer it
    EXCHANGE_QUOTE_PREFERENCE = {
        'coinbase': 'USD',
        'kraken': 'USD',
        'binance': 'USDT',
        'mexc': 'USDT',
        'bybit': 'USDT',
        'okx': 'USDT'
    }
    
    def __init__(self, api_key: str, mapper=None, max_workers: int = 3):
        """
        Initialize Chart-IMG client
        
        Args:
            api_key: Chart-IMG API key
            mapper: TradingViewMapper instance
            max_workers: Maximum concurrent requests
        """
        self.api_key = api_key
        self.mapper = mapper
        self.max_workers = max_workers
        self.logger = logging.getLogger('ChartIMG')
        self.rate_limit_lock = Lock()
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms between requests
        
        if not api_key:
            self.logger.error("❌ No Chart-IMG API key provided")
    
    def _format_tv_symbol(self, coin_symbol: str, exchange: str) -> Optional[str]:
        """
        Format TradingView symbol according to exchange rules
        
        Args:
            coin_symbol: Coin symbol (e.g., 'BTC')
            exchange: Exchange name (e.g., 'coinbase', 'kraken')
            
        Returns:
            Formatted TradingView symbol or None if exchange not supported
        """
        exchange = exchange.lower()
        if exchange not in self.EXCHANGE_FORMATS:
            self.logger.warning(f"⚠️ Unsupported exchange: {exchange}")
            return None
        
        fmt = self.EXCHANGE_FORMATS[exchange]
        quote = self.EXCHANGE_QUOTE_PREFERENCE.get(exchange, 'USD')
        
        # Handle special cases
        if exchange == 'kraken' and coin_symbol in fmt.get('special', {}):
            pair = fmt['special'][coin_symbol]
        else:
            # Apply quote override if needed
            if 'quote_override' in fmt and quote in fmt['quote_override']:
                quote = fmt['quote_override'][quote]
            
            # Format the pair
            if fmt['separator']:
                pair = f"{coin_symbol}{fmt['separator']}{quote}"
            else:
                pair = fmt['format'].format(symbol=coin_symbol, quote=quote)
        
        return f"{fmt['prefix']}:{pair}"
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        with self.rate_limit_lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_request_interval:
                sleep_time = self.min_request_interval - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()
    
    def get_chart(self, coin_symbol: str, exchange: str = None, 
                  interval: str = "1D", width: int = 800, 
                  height: int = 400) -> Optional[bytes]:
        """
        Get a single chart image
        
        Args:
            coin_symbol: Coin symbol (e.g., 'BTC')
            exchange: Preferred exchange (e.g., 'coinbase')
            interval: Chart interval ('1D', '4h', '1h', etc.)
            width: Image width
            height: Image height
            
        Returns:
            PNG image bytes or None if failed
        """
        if not self.api_key:
            self.logger.error("❌ No API key configured")
            return None
        
        # Determine which exchanges to try
        exchanges_to_try = []
        if exchange:
            exchanges_to_try.append(exchange)
        
        # Add fallback exchanges based on quote preference
        if 'coinbase' not in exchanges_to_try:
            exchanges_to_try.append('coinbase')
        if 'binance' not in exchanges_to_try:
            exchanges_to_try.append('binance')
        if 'mexc' not in exchanges_to_try:
            exchanges_to_try.append('mexc')
        
        # Try each exchange until one works
        for ex in exchanges_to_try:
            # Format symbol
            tv_symbol = self._format_tv_symbol(coin_symbol, ex)
            if not tv_symbol:
                continue
            
            self.logger.info(f"📡 Trying {tv_symbol}")
            
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json"
            }
            
            payload = {
                "symbol": tv_symbol,
                "interval": interval,
                "range": "1M",  # 1 month [citation:1]
                "theme": "dark",
                "width": width,
                "height": height,
                "format": "png",
                "studies": []  # No indicators for clean look
            }
            
            try:
                self._rate_limit()
                
                response = requests.post(
                    self.BASE_URL_V2,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    self.logger.info(f"✅ Got chart from {ex}: {len(response.content)} bytes")
                    return response.content
                    
                elif response.status_code == 422:
                    self.logger.warning(f"⚠️ Symbol {tv_symbol} not found on {ex}")
                    continue
                    
                elif response.status_code == 429:
                    self.logger.error(f"❌ Rate limited (429) - waiting longer")
                    time.sleep(5)  # Extra wait on rate limit
                    continue
                    
                else:
                    self.logger.warning(f"⚠️ {ex} failed: HTTP {response.status_code}")
                    continue
                    
            except Exception as e:
                self.logger.error(f"❌ Error with {ex}: {e}")
                continue
        
        self.logger.error(f"❌ No exchange worked for {coin_symbol}")
        return None
    
    def get_charts_batch(self, coins: List[Tuple[str, str]], 
                         interval: str = "1D", 
                         width: int = 800, 
                         height: int = 400) -> Dict[str, Optional[bytes]]:
        """
        Get charts for multiple coins in parallel
        
        Args:
            coins: List of (coin_symbol, preferred_exchange) tuples
            interval: Chart interval
            width: Image width
            height: Image height
            
        Returns:
            Dictionary mapping coin_symbol to chart bytes (or None if failed)
        """
        results = {}
        results_lock = Lock()
        
        def fetch_single(coin_symbol: str, exchange: str) -> Tuple[str, Optional[bytes]]:
            """Fetch a single chart (for threading)"""
            try:
                chart_bytes = self.get_chart(coin_symbol, exchange, interval, width, height)
                return coin_symbol, chart_bytes
            except Exception as e:
                self.logger.error(f"❌ Error fetching {coin_symbol}: {e}")
                return coin_symbol, None
        
        # Use ThreadPoolExecutor for parallel requests [citation:1]
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_coin = {
                executor.submit(fetch_single, coin, exch): coin 
                for coin, exch in coins
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_coin):
                coin_symbol, chart_bytes = future.result()
                with results_lock:
                    results[coin_symbol] = chart_bytes
                
                # Small delay between starting new requests
                time.sleep(0.2)
        
        return results
    
    def get_chart_with_fallback(self, coin_symbol: str, exchanges: List[str] = None) -> Optional[bytes]:
        """
        Try multiple exchanges in order until one works
        
        Args:
            coin_symbol: Coin symbol
            exchanges: List of exchanges to try (in order)
            
        Returns:
            Chart bytes or None
        """
        if not exchanges:
            exchanges = ['coinbase', 'binance', 'mexc', 'kraken']
        
        for exchange in exchanges:
            chart_bytes = self.get_chart(coin_symbol, exchange)
            if chart_bytes:
                return chart_bytes
        
        return None