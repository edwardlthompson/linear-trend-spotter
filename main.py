#!/usr/bin/env python3
"""Linear Trend Spotter - Scans ALL exchange-listed coins"""
import os
import sys
import json
import io
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from config.constants import STABLECOINS
from database.models import HistoryDatabase, ActiveCoinsDatabase
from database.cache import PriceCache
from api.coinmarketcap import CoinMarketCapClient
from api.coingecko import CoinGeckoClient
from api.coingecko_mapper import CoinGeckoMapper
from api.price_history_fallback import PriceHistoryFallbackClient
from api.chart_img import ChartIMGClient
from api.tradingview_mapper import TradingViewMapper
from processors.uniformity_filter import UniformityFilter
from notifications.telegram import TelegramClient
from notifications.formatter import MessageFormatter
from notifications.image_renderer import build_fallback_chart_image, build_combined_notification_image
from backtesting.runner import run_backtests_for_final_results
from backtesting.report import notification_rows_for_symbol
from utils.metrics import metrics, timed_block
from utils.runtime_hygiene import run_artifact_hygiene, update_exit_reason_analytics
from utils.logger import app_logger

# Import exchange database
from exchange_data.exchange_db import ExchangeDatabase
from exchange_data.exchange_fetcher import ExchangeFetcher

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


def aggregate_daily_bars_from_hourly(hourly_rows):
    """Aggregate hourly OHLCV rows into daily bars for OHLCV uniformity scoring."""
    buckets = {}
    for row in hourly_rows:
        ts = int(row['ts'])
        day_key = ts // 86400
        buckets.setdefault(day_key, []).append(row)

    daily_bars = []
    for day_key in sorted(buckets.keys()):
        day_rows = sorted(buckets[day_key], key=lambda item: int(item['ts']))
        if not day_rows:
            continue
        daily_bars.append(
            {
                'open': float(day_rows[0]['open']),
                'high': max(float(item['high']) for item in day_rows),
                'low': min(float(item['low']) for item in day_rows),
                'close': float(day_rows[-1]['close']),
                'volume': sum(float(item.get('volume', 0.0) or 0.0) for item in day_rows),
            }
        )

    return daily_bars


def _build_quality_panel(coin: dict) -> dict:
    score = float(coin.get('uniformity_score', 0.0) or 0.0)
    source = str(coin.get('ohlcv_source', 'unknown'))
    candles = int(coin.get('quality_candles', 0) or 0)

    source_bonus_map = {
        'coingecko_cache': 20,
        'coingecko_api': 18,
        'price_cache': 14,
        'polygon_cache': 12,
        'polygon_api': 10,
    }
    source_bonus = source_bonus_map.get(source, 6)

    if candles >= 720:
        candle_bonus = 20
    elif candles >= 500:
        candle_bonus = 15
    elif candles >= 300:
        candle_bonus = 10
    elif candles > 0:
        candle_bonus = 6
    else:
        candle_bonus = 0

    strategies = coin.get('backtest_top_strategies', []) or []
    buy_hold = coin.get('backtest_buy_hold') or {}
    best_net = None
    if strategies:
        try:
            best_net = max(float(row.get('net_pct', float('-inf'))) for row in strategies)
        except Exception:
            best_net = None

    try:
        bh_net = float(buy_hold.get('net_pct')) if buy_hold else None
    except Exception:
        bh_net = None

    edge_bonus = 0
    if best_net is not None and bh_net is not None:
        if best_net - bh_net >= 10:
            edge_bonus = 18
        elif best_net - bh_net >= 0:
            edge_bonus = 10
        else:
            edge_bonus = 2

    confidence_score = int(round(min(100.0, max(0.0, score * 0.55 + source_bonus + candle_bonus + edge_bonus))))
    confidence = 'High' if confidence_score >= 80 else 'Medium' if confidence_score >= 60 else 'Low'

    return {
        'price_source': source,
        'candles_1h_lookback': candles,
        'backtest_coverage': f"{len(strategies)}/5 strategies" if strategies else 'No strategy rows',
        'confidence': f"{confidence} ({confidence_score}/100)",
    }

def run_scanner():
    """Main orchestration function"""
    app_logger.info("=" * 60)
    app_logger.info("📊 LINEAR TREND SPOTTER (FULL EXCHANGE SCAN)")
    app_logger.info("=" * 60)
    app_logger.info(f"Started: {datetime.now()}")
    app_logger.info(f"Minimum 24h Volume: ${settings.min_volume:,}")
    app_logger.info(f"Uniformity Minimum Score: {settings.uniformity_min_score}")
    app_logger.info("Uniformity Mode: OHLCV-only")
    app_logger.info(f"Scanning ALL coins from: {', '.join(settings.target_exchanges)}")
    
    metrics.reset()

    if settings.artifact_hygiene_enabled:
        try:
            hygiene_result = run_artifact_hygiene(
                settings.base_dir,
                settings.artifact_archive_dir,
                settings.artifact_retention_days,
            )
            if hygiene_result.get('archived_count', 0) > 0:
                app_logger.info(
                    "🧹 Artifact hygiene archived "
                    f"{hygiene_result.get('archived_count', 0)} files to {hygiene_result.get('archive_dir')}"
                )
        except Exception as hygiene_error:
            app_logger.warning(f"⚠️ Artifact hygiene failed: {hygiene_error}")
    
    try:
        # Initialize components
        with timed_block('initialization'):
            history_db = HistoryDatabase(settings.db_paths['scanner'])
            active_db = ActiveCoinsDatabase(settings.db_paths['scanner'])
            cache = PriceCache(settings.db_paths['scanner'])
            
            exchange_db_path = settings.db_paths['exchanges']
            exchange_db = ExchangeDatabase(exchange_db_path)
            
            tv_mapper_db_path = settings.db_paths['tv_mappings']
            tv_mapper = TradingViewMapper(tv_mapper_db_path)
            
            # Initialize CoinMarketCap client (for gains)
            cmc = CoinMarketCapClient(settings.cmc_api_key)
            app_logger.info("✅ CoinMarketCap client initialized")
            
            # Initialize CoinGecko client (for exchange volumes only)
            gecko = CoinGeckoClient(calls_per_minute=settings.coingecko_calls_per_minute)
            app_logger.info("✅ CoinGecko client initialized")

            # Initialize fallback providers for OHLCV reliability chain
            history_fallback = PriceHistoryFallbackClient(
                polygon_api_key=os.getenv('POLYGON_API_KEY', ''),
                cmc_api_key=settings.cmc_api_key
            )
            app_logger.info("✅ OHLCV fallback chain initialized (Polygon hourly)")
            
            # Initialize CoinGecko Mapper
            cg_mapper_db_path = settings.db_paths['mappings']
            cg_mapper = CoinGeckoMapper(cg_mapper_db_path)
            
            stats = cg_mapper.get_stats()
            if stats['total_mappings'] == 0:
                app_logger.info("📡 CoinGecko mappings empty, fetching...")
                cg_mapper.update_mappings()
            else:
                app_logger.info(f"✅ CoinGecko mapper ready with {stats['total_mappings']} mappings")
            
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
                app_logger.info("✅ Telegram client initialized")
            else:
                app_logger.warning("⚠️ Telegram credentials missing - notifications disabled")
        
        # ============================================================
        # STEP 1: Get top configured coins with gains from CoinMarketCap
        # ============================================================
        app_logger.info("\n📡 Fetching all coins with gains from CoinMarketCap...")
        
        all_cmc_coins = cmc.get_all_coins_with_gains(limit=settings.top_coins_limit)
        
        if not all_cmc_coins:
            app_logger.error("❌ Failed to fetch coins from CMC")
            tv_mapper.close()
            exchange_db.close()
            cg_mapper.close()
            return
        
        app_logger.info(f"✅ Got {len(all_cmc_coins)} coins with gain data")
        metrics.increment('coins_retrieved', len(all_cmc_coins))
        
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
            app_logger.warning("   No exchange data found. Attempting one-time exchange listings refresh...")
            try:
                ExchangeFetcher(exchange_db).update_all_exchanges()

                import sqlite3
                conn = sqlite3.connect(exchange_db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT symbol FROM exchange_listings')
                for row in cursor.fetchall():
                    all_symbols.add(row[0])
                conn.close()

                if all_symbols:
                    app_logger.info(f"   ✓ Exchange listings refreshed: {len(all_symbols)} symbols")
            except Exception as refresh_error:
                app_logger.warning(f"   Exchange listings refresh failed: {refresh_error}")

        if not all_symbols:
            app_logger.warning("   No exchange data found after refresh - using default list")
            all_symbols = {'BTC', 'ETH', 'SOL', 'XRP'}
        
        all_symbols_set = set(all_symbols)
        all_symbols = list(all_symbols)
        app_logger.info(f"   ✓ Scanning ALL {len(all_symbols)} coins from exchange listings")

        # ============================================================
        # STEP 3: Match with CMC data and apply volume/gain filters
        # ============================================================
        app_logger.info(f"\n💰 FILTER 1: Applying volume and gain filters...")
        
        gain_qualified = []
        
        for symbol in all_symbols:
            # Filter out stablecoins per spec §5.5
            if symbol in STABLECOINS:
                app_logger.info(f"   ⏭️ {symbol}: Skipped (stablecoin)")
                continue
                
            if symbol in cmc_by_symbol:
                cmc_data = cmc_by_symbol[symbol]
                gains = cmc_data['gains']
                info = cmc_data['info']
                
                # Check volume filter
                if info['volume_24h'] >= settings.min_volume:
                    # Check gain filter:
                    # - 7d > 7%
                    # - 30d > 30%
                    # - 30d must be higher than 7d
                    if gains['7d'] > 7 and gains['30d'] > 30 and gains['30d'] > gains['7d']:
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
        metrics.increment('gain_filter_passed', len(gain_qualified))

        gain_qualified_symbols = {c['symbol'] for c in gain_qualified}
        
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

        coins_with_cg_ids_symbols = {c['symbol'] for c in coins_with_cg_ids}
        
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

            found_cached_volumes, cached_volumes = cache.get_exchange_volumes(coin['cg_id'])
            if found_cached_volumes and cached_volumes:
                coin['exchange_volumes'] = cached_volumes
                app_logger.info(f"      ✓ Using cached exchange volumes")
                continue
            
            tickers = gecko.get_tickers(coin['cg_id'])
            
            if tickers:
                volumes = process_tickers(tickers, settings.target_exchanges)
                coin['exchange_volumes'] = volumes
                cache.cache_exchange_volumes(coin['cg_id'], volumes)
                app_logger.info(f"      ✓ Got exchange volumes")
            else:
                coin['exchange_volumes'] = {ex: "N/A" for ex in settings.target_exchanges}
                app_logger.info(f"      ⚠️ No ticker data")

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
                coin['ohlcv_source'] = 'price_cache'
                coin['quality_candles'] = 0
                cached_coins.append(coin)
                app_logger.info(f"   ✓ {coin['symbol']}: Using cached (score: {cached['uniformity_score']:.1f})")
            else:
                uncached_coins.append(coin)
        
        app_logger.info(f"\n   Cached: {len(cached_coins)}, Need fetching: {len(uncached_coins)}")
        
        # Process uncached coins (OHLCV-only uniformity)
        uniformity_days = settings.uniformity_period
        for i, coin in enumerate(uncached_coins, 1):
            app_logger.info(f"\n   [{i}/{len(uncached_coins)}] {coin['symbol']}")

            ohlcv_source = 'none'
            found, cached_rows = cache.get_ohlcv_rows('coingecko', coin['symbol'], '1h', max_age_hours=settings.cache_price_hours)
            hourly_rows = cached_rows if found and cached_rows else None
            if hourly_rows:
                ohlcv_source = 'coingecko_cache'
            else:
                api_rows = gecko.get_hourly_ohlcv(coin['cg_id'], days=max(30, uniformity_days))
                if api_rows:
                    cache.cache_ohlcv_rows('coingecko', coin['symbol'], '1h', api_rows, source='coingecko_api')
                    hourly_rows = api_rows
                    ohlcv_source = 'coingecko_api'

            if not hourly_rows:
                found_polygon, cached_polygon_rows = cache.get_ohlcv_rows('polygon', coin['symbol'], '1h', max_age_hours=settings.cache_price_hours)
                if found_polygon and cached_polygon_rows:
                    hourly_rows = cached_polygon_rows
                    ohlcv_source = 'polygon_cache'
                else:
                    polygon_rows = history_fallback.get_polygon_30d_hourly_ohlcv(coin['symbol'])
                    if polygon_rows:
                        cache.cache_ohlcv_rows('polygon', coin['symbol'], '1h', polygon_rows, source='polygon_api')
                        hourly_rows = polygon_rows
                        ohlcv_source = 'polygon_api'

            if not hourly_rows:
                app_logger.info("      ⏳ No OHLCV data available - will retry next scan")
                continue

            coin['quality_candles'] = len(hourly_rows)
            coin['ohlcv_source'] = ohlcv_source

            daily_bars = aggregate_daily_bars_from_hourly(hourly_rows)
            if len(daily_bars) < uniformity_days:
                app_logger.info("      ⚠️ Insufficient OHLCV history")
                continue

            score, gain = UniformityFilter.calculate_from_ohlcv(daily_bars, uniformity_days)
            coin['uniformity_score'] = score
            coin['total_gain'] = gain

            closes_for_cache = [float(bar['close']) for bar in daily_bars[-uniformity_days:]]
            cache.cache_price_data(coin['cg_id'], closes_for_cache, score, gain)
            app_logger.info(f"      ✅ Score: {score:.1f}, Return: {gain:+.1f}% ({ohlcv_source})")
        
        # Combine all processed coins
        all_processed = cached_coins + [c for c in uncached_coins if 'uniformity_score' in c]
        all_processed_map = {c['symbol']: c for c in all_processed}

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

        uniformity_passed_symbols = {c['symbol'] for c in uniformity_passed}

        # ============================================================
        # STEP 9: Sort and process final results
        # ============================================================
        final_results = sorted(uniformity_passed, 
                              key=lambda x: x['uniformity_score'], 
                              reverse=True)

        # ============================================================
        # STEP 9.1: Optional backtesting run (feature-flagged)
        # ============================================================
        backtest_summary = None
        if settings.backtest_enabled:
            app_logger.info("\n🧪 Running backtests for final-stage qualified coins...")
            try:
                backtest_summary = run_backtests_for_final_results(final_results)
                app_logger.info(
                    "   ✅ Backtests complete: "
                    f"eligible={backtest_summary.get('coins_eligible', 0)}, "
                    f"processed={backtest_summary.get('coins_processed', 0)}, "
                    f"failed={backtest_summary.get('coins_failed', 0)}, "
                    f"rows={backtest_summary.get('rows_generated', 0)}"
                )
                if backtest_summary.get('resumed_from_checkpoint'):
                    app_logger.info(
                        "   ♻️ Resume active: "
                        f"{backtest_summary.get('resumed_completed_symbols', 0)} symbols loaded from checkpoint"
                    )
                failure_breakdown = backtest_summary.get('failure_breakdown', {}) or {}
                if failure_breakdown:
                    app_logger.info(f"   📉 Failure breakdown: {failure_breakdown}")
                metrics.increment('backtests_processed', int(backtest_summary.get('coins_processed', 0)))
            except Exception as backtest_error:
                app_logger.error(f"   ❌ Backtesting failed: {backtest_error}")
                app_logger.info("   ℹ️ Continuing scanner flow despite backtesting failure")

        if backtest_summary:
            for coin in final_results:
                symbol = coin.get('symbol', '')
                if not symbol:
                    continue
                details = notification_rows_for_symbol(backtest_summary, symbol, top_n=5)
                coin['backtest_top_strategies'] = details.get('top_strategies', [])
                coin['backtest_buy_hold'] = details.get('buy_hold')
        
        # Check entries/exits
        app_logger.info("\n🔄 Checking for entries/exits...")
        entered, exited = active_db.get_entered_exited(final_results)
        app_logger.info(f"   New entries: {len(entered)}, Exits: {len(exited)}")
        app_logger.info(
            "   Notification toggles: "
            f"entry={settings.entry_notifications}, "
            f"exit={settings.exit_notifications}, "
            f"no_change={settings.no_change_notifications}"
        )
        if not telegram:
            app_logger.info("   Telegram status: disabled (missing TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID)")
        else:
            app_logger.info("   Telegram status: enabled")

        if entered:
            fallback_summary = backtest_summary
            if not fallback_summary:
                artifact_path = settings.base_dir / "backtest_results.json"
                if artifact_path.exists():
                    try:
                        with artifact_path.open("r", encoding="utf-8") as handle:
                            fallback_summary = json.load(handle)
                    except Exception as artifact_error:
                        app_logger.warning(f"   ⚠️ Could not read backtest artifact for notifications: {artifact_error}")

            if fallback_summary:
                for coin in entered:
                    if coin.get('backtest_top_strategies') and coin.get('backtest_buy_hold'):
                        continue
                    symbol = coin.get('symbol', '')
                    if not symbol:
                        continue
                    details = notification_rows_for_symbol(fallback_summary, symbol, top_n=5)
                    coin['backtest_top_strategies'] = details.get('top_strategies', [])
                    coin['backtest_buy_hold'] = details.get('buy_hold')

        # Attach precise exit reasons based on first failed pipeline stage
        for coin in exited:
            symbol = coin['symbol']

            if symbol in STABLECOINS:
                coin['exit_reason'] = "Filtered as stablecoin"
                continue

            if symbol not in all_symbols_set:
                coin['exit_reason'] = "No longer listed on target exchanges"
                continue

            cmc_data = cmc_by_symbol.get(symbol)
            if not cmc_data:
                coin['exit_reason'] = "Missing from current CoinMarketCap snapshot"
                continue

            gains = cmc_data['gains']
            info = cmc_data['info']

            if info['volume_24h'] < settings.min_volume:
                coin['exit_reason'] = (
                    f"24h volume below threshold (${info['volume_24h']:,.0f} < ${settings.min_volume:,.0f})"
                )
                continue

            gain_7d = gains.get('7d', 0)
            gain_30d = gains.get('30d', 0)
            if gain_7d <= 7:
                coin['exit_reason'] = f"7d gain below threshold ({gain_7d:.1f}% ≤ 7.0%)"
                continue
            if gain_30d <= 30:
                coin['exit_reason'] = f"30d gain below threshold ({gain_30d:.1f}% ≤ 30.0%)"
                continue
            if gain_30d <= gain_7d:
                coin['exit_reason'] = f"30d gain not higher than 7d ({gain_30d:.1f}% ≤ {gain_7d:.1f}%)"
                continue

            if symbol not in gain_qualified_symbols:
                coin['exit_reason'] = "Failed gain/volume filter"
                continue

            if symbol not in coins_with_cg_ids_symbols:
                coin['exit_reason'] = "No CoinGecko ID mapping"
                continue

            if symbol not in all_processed_map:
                coin['exit_reason'] = "Insufficient or missing 30d price history"
                continue

            processed_coin = all_processed_map[symbol]
            if processed_coin.get('uniformity_score', 0) < settings.uniformity_min_score:
                coin['exit_reason'] = (
                    f"Uniformity score below threshold ({processed_coin.get('uniformity_score', 0):.1f} < {settings.uniformity_min_score})"
                )
                continue

            if processed_coin.get('total_gain', 0) <= 0:
                coin['exit_reason'] = f"30d return non-positive ({processed_coin.get('total_gain', 0):.1f}%)"
                continue

            if symbol not in uniformity_passed_symbols:
                coin['exit_reason'] = "Failed final uniformity qualification"
                continue

            coin['exit_reason'] = "No longer met qualification criteria"

        try:
            analytics = update_exit_reason_analytics(settings.exit_analytics_file, exited)
            if exited:
                app_logger.info(
                    "📈 Exit analytics updated: "
                    f"run_exits={analytics.get('last_run', {}).get('exits', 0)}, "
                    f"total_exits={analytics.get('total_exits', 0)}"
                )
        except Exception as analytics_error:
            app_logger.warning(f"⚠️ Exit analytics update failed: {analytics_error}")
        
        # ============================================================
        # STEP 10: Send Telegram notifications with chart images
        # ============================================================
        if telegram and entered and settings.entry_notifications:
            with timed_block('notifications'):
                app_logger.info(f"\n📱 Sending entry notifications for {len(entered)} new coins...")

                if settings.notification_include_quality_panel:
                    for coin in entered:
                        coin['quality_panel'] = _build_quality_panel(coin)
                
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

                    if not chart_bytes:
                        chart_bytes = build_fallback_chart_image(coin['symbol'], settings.db_paths['scanner'])
                        if chart_bytes:
                            app_logger.info("      ℹ️ Using cached OHLCV fallback chart")
                    
                    # Use MessageFormatter per spec §10.1
                    caption = MessageFormatter.format_entry(coin)
                    
                    # Send one combined image notification (chart + strategy table)
                    if chart_bytes:
                        combined_image = build_combined_notification_image(coin, chart_bytes)
                        image_payload = combined_image if combined_image else chart_bytes
                        img_data = io.BytesIO(image_payload)
                        message_id = telegram.send_photo(img_data, caption=caption)
                        if message_id:
                            app_logger.info(f"      📤 Sent combined image notification")
                        else:
                            app_logger.error(f"      ❌ Failed to send combined image notification")
                    else:
                        message_id = telegram.send_message(caption)
                        if message_id:
                            app_logger.info(f"      📤 Sent text-only notification")
                        else:
                            app_logger.error(f"      ❌ Failed to send text-only notification")
                    
                    metrics.increment('notifications_sent')
        
        if telegram and exited and settings.exit_notifications:
            app_logger.info(f"\n📱 Sending exit notifications for {len(exited)} coins...")
            for coin in exited:
                app_logger.info(f"   🔴 Exit: {coin['symbol']}")
                # Use MessageFormatter per spec §10.2
                message = MessageFormatter.format_exit(coin)
                telegram.send_message(message)
                metrics.increment('notifications_sent')

        if telegram and not entered and not exited and settings.no_change_notifications:
            app_logger.info("\n📱 Sending no-change scan summary notification...")
            summary_message = (
                "ℹ️ <b>Scan complete</b>\n"
                f"No entries or exits this cycle.\n"
                f"Qualified coins: {len(final_results)}"
            )
            telegram.send_message(summary_message)
            metrics.increment('notifications_sent')
        elif telegram and not entered and not exited and not settings.no_change_notifications:
            app_logger.info("ℹ️ No notifications sent: no entries/exits and NO_CHANGE_NOTIFICATIONS=false")
        elif not telegram and (entered or exited):
            app_logger.warning("⚠️ Entry/exit events detected but Telegram is disabled")
        
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