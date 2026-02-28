#!/usr/bin/env python3
"""Linear Trend Spotter - Scans ALL exchange-listed coins"""
import os
import sys
import time
import io
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from database.models import HistoryDatabase, ActiveCoinsDatabase
from database.cache import CoinLoreCache
from api.coinmarketcap import CoinMarketCapClient
from api.coingecko_optimized import CoinGeckoOptimizedClient
from api.coingecko_mapper import CoinGeckoMapper
from api.chart_img import ChartIMGClient
from api.tradingview_mapper import TradingViewMapper
from processors.gain_filter import GainFilter
from processors.uniformity_filter import UniformityFilter
from notifications.telegram import TelegramClient
from notifications.formatter import MessageFormatter
from utils.metrics import metrics, timed_block
from utils.logger import app_logger

# Import exchange database
from exchange_data.exchange_db import ExchangeDatabase

class RateLimiter:
    """Intelligent rate limiter with exponential backoff"""
    def __init__(self, calls_per_minute=30):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time = 0
        self.consecutive_429s = 0
        self.max_backoff = 300
        
    def wait_if_needed(self):
        now = time.time()
        time_since_last = now - self.last_call_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
        else:
            wait_time = 0
        
        if self.consecutive_429s > 0:
            backoff_time = min(2 ** self.consecutive_429s, self.max_backoff)
            wait_time = max(wait_time, backoff_time)
            app_logger.info(f"      ⏱️  Backoff active: +{backoff_time}s")
        
        if wait_time > 0:
            time.sleep(wait_time)
        
        self.last_call_time = time.time()
    
    def record_success(self):
        self.consecutive_429s = 0
    
    def record_429(self):
        self.consecutive_429s += 1
        app_logger.warning(f"      ⚠️ Rate limit hit ({self.consecutive_429s}x)")

def process_tickers(tickers_data, target_exchanges):
    """Process ticker data to extract exchange volumes"""
    volumes = {ex: "N/A" for ex in target_exchanges}
    
    if not tickers_data or 'tickers' not in tickers_data:
        return volumes
    
    for ticker in tickers_data.get('tickers', []):
        exchange_id = ticker.get('market', {}).get('identifier', '').lower()
        exchange_name = ticker.get('market', {}).get('name', '').lower()
        volume = float(ticker.get('converted_volume', {}).get('usd', 0))
        
        for target in target_exchanges:
            if target in exchange_id or target in exchange_name:
                if volumes[target] == "N/A" or volume > volumes[target]:
                    volumes[target] = volume
    
    return volumes

def run_scanner():
    """Main orchestration function"""
    app_logger.info("=" * 60)
    app_logger.info("📊 LINEAR TREND SPOTTER (FULL EXCHANGE SCAN)")
    app_logger.info("=" * 60)
    app_logger.info(f"Started: {datetime.now()}")
    app_logger.info(f"Minimum 24h Volume: ${settings.min_volume:,}")
    app_logger.info(f"Uniformity Minimum Score: {settings.uniformity_min_score}")
    app_logger.info(f"Scanning ALL coins from: {', '.join(settings.target_exchanges)}")
    
    metrics.reset()
    
    try:
        # Initialize components
        with timed_block('initialization'):
            history_db = HistoryDatabase(settings.db_paths['history'])
            active_db = ActiveCoinsDatabase(settings.db_paths['history'])
            cache = CoinLoreCache(settings.db_paths['history'])
            
            exchange_db_path = settings.db_paths['history'].parent / 'exchange_listings.db'
            exchange_db = ExchangeDatabase(exchange_db_path)
            
            tv_mapper_db_path = settings.db_paths['history'].parent / 'tv_mappings.db'
            tv_mapper = TradingViewMapper(tv_mapper_db_path)
            
            # Initialize CoinMarketCap client (for gains)
            cmc = CoinMarketCapClient(settings.cmc_api_key)
            app_logger.info("✅ CoinMarketCap client initialized")
            
            # Initialize CoinGecko client (for exchange volumes only)
            gecko = CoinGeckoOptimizedClient()
            app_logger.info("✅ CoinGecko client initialized")
            
            # Initialize CoinGecko Mapper
            cg_mapper_db_path = settings.db_paths['history'].parent / 'coingecko_mappings.db'
            cg_mapper = CoinGeckoMapper(cg_mapper_db_path)
            
            stats = cg_mapper.get_stats()
            if stats['total_mappings'] == 0:
                app_logger.info("📡 CoinGecko mappings empty, fetching...")
                cg_mapper.update_mappings()
            else:
                app_logger.info(f"✅ CoinGecko mapper ready with {stats['total_mappings']} mappings")
            
            rate_limiter = RateLimiter(calls_per_minute=25)
            
            # Initialize Chart-IMG client
            chart_img = None
            if settings.chart_img_api_key:
                chart_img = ChartIMGClient(settings.chart_img_api_key, mapper=tv_mapper)
                app_logger.info("✅ Chart-IMG client initialized")
            else:
                app_logger.warning("⚠️ No Chart-IMG API key - charts disabled")
            
            # Initialize Telegram
            telegram = None
            if settings.telegram:
                telegram = TelegramClient(
                    settings.telegram['bot_token'],
                    settings.telegram['chat_id']
                )
        
        # ============================================================
        # STEP 1: Get ALL coins with gains from CoinMarketCap (5000 coins)
        # ============================================================
        app_logger.info("\n📡 Fetching all coins with gains from CoinMarketCap...")
        
        all_cmc_coins = cmc.get_all_coins_with_gains(limit=5000)
        
        if not all_cmc_coins:
            app_logger.error("❌ Failed to fetch coins from CMC")
            tv_mapper.close()
            exchange_db.close()
            cg_mapper.close()
            return
        
        app_logger.info(f"✅ Got {len(all_cmc_coins)} coins with gain data")
        
        # Build lookup dict for quick access
        cmc_by_symbol = {}
        for coin in all_cmc_coins:
            symbol = coin.get('symbol', '').upper()
            if symbol:
                cmc_by_symbol[symbol] = {
                    'data': coin,
                    'gains': cmc.extract_gains(coin),
                    'info': cmc.extract_coin_data(coin)
                }
        
        app_logger.info(f"📊 Built lookup for {len(cmc_by_symbol)} symbols")

        # ============================================================
        # STEP 2: Get ALL symbols from exchange listings (no limit!)
        # ============================================================
        app_logger.info("\n🔍 Getting ALL token symbols from exchange listings...")
        
        all_symbols = set()
        
        if exchange_db_path.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(exchange_db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT symbol FROM exchange_listings')
                for row in cursor.fetchall():
                    all_symbols.add(row[0])
                conn.close()
                app_logger.info(f"   ✓ Found {len(all_symbols)} unique symbols across all exchanges")
            except Exception as e:
                app_logger.warning(f"   Could not query exchange_listings: {e}")
        
        # Fallback if no exchange data (shouldn't happen with proper setup)
        if not all_symbols:
            app_logger.warning("   No exchange data found - using default list")
            all_symbols = {'BTC', 'ETH', 'SOL', 'XRP'}
        
        all_symbols = list(all_symbols)
        app_logger.info(f"   ✓ Scanning ALL {len(all_symbols)} coins from exchange listings")

        # ============================================================
        # STEP 3: Match with CMC data and apply volume/gain filters
        # ============================================================
        app_logger.info(f"\n💰 FILTER 1: Applying volume and gain filters...")
        
        gain_qualified = []
        
        for symbol in all_symbols:
            if symbol in cmc_by_symbol:
                cmc_data = cmc_by_symbol[symbol]
                gains = cmc_data['gains']
                info = cmc_data['info']
                
                # Check volume filter
                if info['volume_24h'] >= settings.min_volume:
                    # Check gain filter (7d > 7% and 30d > 30%)
                    if gains['7d'] > 7 and gains['30d'] > 30:
                        coin_info = {
                            'symbol': symbol,
                            'name': info['name'],
                            'slug': info['slug'],
                            'gains': gains,
                            'volume_24h': info['volume_24h'],
                        }
                        gain_qualified.append(coin_info)
                        app_logger.info(f"   ✓ {symbol}: 7d:{gains['7d']:.1f}% 30d:{gains['30d']:.1f}% Vol:${info['volume_24h']:,.0f}")
                    else:
                        app_logger.info(f"   ❌ {symbol}: Gains too low (7d:{gains['7d']:.1f}% 30d:{gains['30d']:.1f}%)")
                else:
                    app_logger.info(f"   ❌ {symbol}: Volume too low (${info['volume_24h']:,.0f})")
            else:
                app_logger.info(f"   ❌ {symbol}: Not found in CMC data")
        
        app_logger.info(f"\n   ✅ PASSED gain filter: {len(gain_qualified)} coins")
        
        if not gain_qualified:
            app_logger.warning("No coins passed gain filter")
            tv_mapper.close()
            exchange_db.close()
            cg_mapper.close()
            return

        # ============================================================
        # STEP 4: Get exchange listing data (for volume display)
        # ============================================================
        app_logger.info(f"\n🏦 Getting exchange listing data...")
        
        for coin in gain_qualified:
            listed_on = []
            for exchange in settings.target_exchanges:
                if exchange_db.is_listed(coin['symbol'], exchange):
                    listed_on.append(exchange)
            coin['listed_on'] = listed_on

        # ============================================================
        # STEP 5: Get CoinGecko IDs for exchange volumes
        # ============================================================
        app_logger.info(f"\n🔍 Getting CoinGecko IDs for {len(gain_qualified)} coins...")
        
        coins_with_cg_ids = []
        coins_without_cg_ids = []
        
        for coin in gain_qualified:
            cg_id = cg_mapper.get_coin_id(coin['symbol'])
            if cg_id:
                coin['cg_id'] = cg_id
                coin['gecko_id'] = cg_id
                coins_with_cg_ids.append(coin)
            else:
                coins_without_cg_ids.append(coin['symbol'])
        
        app_logger.info(f"   Found CoinGecko IDs for {len(coins_with_cg_ids)} coins")
        
        if not coins_with_cg_ids:
            app_logger.warning("No coins with CoinGecko IDs")
            tv_mapper.close()
            exchange_db.close()
            cg_mapper.close()
            return

        # ============================================================
        # STEP 6: Get exchange volume data from CoinGecko
        # ============================================================
        app_logger.info(f"\n💱 Fetching exchange volume data for {len(coins_with_cg_ids)} coins...")
        
        for i, coin in enumerate(coins_with_cg_ids, 1):
            app_logger.info(f"   [{i}/{len(coins_with_cg_ids)}] {coin['symbol']}")
            
            rate_limiter.wait_if_needed()
            
            tickers = gecko.get_tickers(coin['cg_id'])
            
            if tickers:
                volumes = process_tickers(tickers, settings.target_exchanges)
                coin['exchange_volumes'] = volumes
                app_logger.info(f"      ✓ Got exchange volumes")
                rate_limiter.record_success()
            else:
                coin['exchange_volumes'] = {ex: "N/A" for ex in settings.target_exchanges}
                app_logger.info(f"      ⚠️ No ticker data")
                rate_limiter.record_429()

        # ============================================================
        # STEP 7: Calculate uniformity scores
        # ============================================================
        app_logger.info(f"\n📐 FILTER 2: Calculating uniformity scores...")
        
        # Check cache first
        cached_coins = []
        uncached_coins = []
        
        for coin in coins_with_cg_ids:
            found, cached = cache.get_price_data(coin['cg_id'])
            if found and cached:
                coin['uniformity_score'] = cached['uniformity_score']
                coin['total_gain'] = cached['gains_30d']
                cached_coins.append(coin)
                app_logger.info(f"   ✓ {coin['symbol']}: Using cached (score: {cached['uniformity_score']:.1f})")
            else:
                uncached_coins.append(coin)
        
        app_logger.info(f"\n   Cached: {len(cached_coins)}, Need fetching: {len(uncached_coins)}")
        
        # Process uncached coins
        for i, coin in enumerate(uncached_coins, 1):
            app_logger.info(f"\n   [{i}/{len(uncached_coins)}] {coin['symbol']}")
            
            rate_limiter.wait_if_needed()
            
            prices = gecko.get_market_chart(coin['cg_id'], 30)
            
            if prices is None:
                rate_limiter.record_429()
                app_logger.info(f"      ⏳ Rate limited - will retry next scan")
                continue
            
            if prices and len(prices) >= 30:
                score, gain = UniformityFilter.calculate(prices, 30)
                
                coin['uniformity_score'] = score
                coin['total_gain'] = gain
                
                # Cache the results
                cache.cache_price_data(coin['cg_id'], prices, score, 
                                     gain, gain, gain)
                app_logger.info(f"      ✅ Score: {score:.1f}, Return: {gain:+.1f}%")
                rate_limiter.record_success()
            else:
                app_logger.info(f"      ⚠️ No price data")
                rate_limiter.record_success()
        
        # Combine all processed coins
        all_processed = cached_coins + [c for c in uncached_coins if 'uniformity_score' in c]

        # ============================================================
        # STEP 8: Apply uniformity filter
        # ============================================================
        app_logger.info(f"\n📐 FILTER 3: Applying uniformity filter (min: {settings.uniformity_min_score})...")
        
        uniformity_passed = []
        
        for coin in all_processed:
            if 'uniformity_score' in coin and coin['uniformity_score'] >= settings.uniformity_min_score and coin['total_gain'] > 0:
                uniformity_passed.append(coin)
                app_logger.info(f"   ✓ {coin['symbol']}: Score {coin['uniformity_score']:.1f}")
            else:
                app_logger.info(f"   ❌ {coin['symbol']}: Failed uniformity")

        # ============================================================
        # STEP 9: Sort and process final results
        # ============================================================
        final_results = sorted(uniformity_passed, 
                              key=lambda x: x['uniformity_score'], 
                              reverse=True)
        
        # Check entries/exits
        app_logger.info("\n🔄 Checking for entries/exits...")
        entered, exited = active_db.get_entered_exited(final_results)
        app_logger.info(f"   New entries: {len(entered)}, Exits: {len(exited)}")
        
        # ============================================================
        # STEP 10: Send Telegram notifications with chart images
        # ============================================================
        if telegram and entered:
            with timed_block('notifications'):
                app_logger.info(f"\n📱 Sending notifications for {len(entered)} new coins...")
                
                for coin in entered:
                    app_logger.info(f"   🟢 {coin['symbol']}")
                    
                    # Get chart image from Chart-IMG (external service)
                    chart_bytes = None
                    if chart_img:
                        try:
                            chart_bytes = chart_img.get_chart(
                                coin_symbol=coin['symbol'],
                                exchange='mexc',
                                interval="1D",
                                width=800,
                                height=400
                            )
                        except Exception as e:
                            app_logger.error(f"      ❌ Chart error: {e}")
                    
                    # Format message with gains
                    cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
                    uni_score = coin.get('uniformity_score', 0)
                    
                    # Get gain values
                    gain_7d = coin['gains'].get('7d', 0)
                    gain_30d = coin['gains'].get('30d', 0)
                    
                    caption = (
                        f"🟢 <a href='{cmc_url}'>{coin['symbol']} ({coin['name']})</a>\n\n"
                        f"📊 Gains:\n"
                        f"   7d: +{gain_7d:.1f}%\n"
                        f"   30d: +{gain_30d:.1f}%\n\n"
                        f"📈 Uniformity Score: {uni_score}/100\n\n"
                        f"💰 Exchange Volumes:\n"
                    )
                    
                    # Add exchange volumes
                    volumes = coin.get('exchange_volumes', {})
                    for exchange in coin.get('listed_on', []):
                        volume = volumes.get(exchange, "N/A")
                        if exchange == 'coinbase':
                            emoji = "🟦"
                        elif exchange == 'kraken':
                            emoji = "🐙"
                        else:
                            emoji = "🟪"
                        
                        if volume != "N/A" and volume != 0:
                            if isinstance(volume, (int, float)):
                                caption += f"{emoji} {exchange.title()}: ${volume:,.0f}\n"
                            else:
                                caption += f"{emoji} {exchange.title()}: {volume}\n"
                        else:
                            caption += f"{emoji} {exchange.title()}: No volume\n"
                    
                    # Send with chart image
                    if chart_bytes:
                        img_data = io.BytesIO(chart_bytes)
                        telegram.send_photo(img_data, caption=caption)
                        app_logger.info(f"      📤 Sent chart image with notification")
                    else:
                        telegram.send_message(caption)
                        app_logger.info(f"      📤 Sent text-only notification")
                    
                    metrics.increment('notifications_sent')
        
        if telegram and exited:
            for coin in exited:
                app_logger.info(f"   🔴 Exit: {coin['symbol']}")
                cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
                message = f"🔴 <a href='{cmc_url}'>{coin['symbol']} ({coin['name']})</a> has left the qualified list"
                telegram.send_message(message)
                metrics.increment('notifications_sent')
        
        # Save results
        if final_results:
            history_db.save_scan(final_results)
            app_logger.info(f"\n📊 Saved {len(final_results)} results")
        
        # Summary
        app_logger.info("\n" + "=" * 60)
        app_logger.info("📊 FILTER SUMMARY")
        app_logger.info("=" * 60)
        app_logger.info(f"Total exchange symbols:  {len(all_symbols)}")
        app_logger.info(f"After Gain/Volume Filter: {len(gain_qualified)}")
        app_logger.info(f"After Uniformity Filter:   {len(final_results)}")
        app_logger.info("=" * 60)
        
        app_logger.info(metrics.report())
        
        stats = cache.get_coin_list_stats()
        app_logger.info(f"\n📊 Cache Summary:")
        app_logger.info(f"   Coin list: {stats['total_coins']} coins")
        app_logger.info(f"   Last updated: {stats['last_update'][:16] if stats['last_update'] != 'Never' else 'Never'}")
        
        metrics.save(settings.metrics_file)
        app_logger.info(f"\n✅ Scan complete")
        
        tv_mapper.close()
        exchange_db.close()
        cg_mapper.close()
        cache.close()
        
    except Exception as e:
        app_logger.error(f"Scan failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    run_scanner()