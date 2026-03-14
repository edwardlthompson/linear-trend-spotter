#!/usr/bin/env python3
"""Linear Trend Spotter - Scans ALL exchange-listed coins"""
import os
import sys
import json
import io
from datetime import datetime, timezone, timedelta
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
from notifications.image_renderer import (
    build_fallback_chart_image,
    build_combined_notification_image,
    build_exit_notification_image,
    build_hourly_summary_image,
)
from backtesting.data_loader import BacktestDataLoader
from backtesting.runner import run_backtests_for_final_results
from backtesting.report import notification_rows_for_symbol
from backtesting.signals import generate_indicator_signals
from utils.insights import (
    build_watchlist,
    compute_data_reliability,
    compute_health_score,
    compute_reentry_quality,
    detect_regime,
    update_scanner_insights,
)
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


def _attach_rank_movement(final_results: list[dict], previous_rank_map: dict[str, int]) -> None:
    for rank, coin in enumerate(final_results, start=1):
        symbol = str(coin.get('symbol', '')).upper()
        previous_rank = previous_rank_map.get(symbol)
        coin['current_rank'] = rank
        coin['previous_rank'] = previous_rank
        if previous_rank is None:
            coin['rank_status'] = 'new'
            coin['rank_delta'] = None
        else:
            delta = previous_rank - rank
            coin['rank_delta'] = delta
            if delta > 0:
                coin['rank_status'] = 'up'
            elif delta < 0:
                coin['rank_status'] = 'down'
            else:
                coin['rank_status'] = 'flat'


def _pct_change(current_value: float, baseline_value: float) -> float | None:
    try:
        current = float(current_value)
        baseline = float(baseline_value)
    except Exception:
        return None
    if baseline <= 0:
        return None
    return ((current - baseline) / baseline) * 100.0


def _format_time_on_list(entered_date_raw: str | None) -> str:
    entered_date = str(entered_date_raw or '').strip()
    if not entered_date:
        return "n/a"
    try:
        entered_at = datetime.fromisoformat(entered_date.replace('Z', '+00:00'))
    except Exception:
        return "n/a"

    if entered_at.tzinfo is None:
        entered_at = entered_at.replace(tzinfo=timezone.utc)

    elapsed = datetime.now(timezone.utc) - entered_at.astimezone(timezone.utc)
    if elapsed.total_seconds() < 0:
        return "n/a"

    total_hours = int(elapsed.total_seconds() // 3600)
    days = total_hours // 24
    hours = total_hours % 24
    if days > 0:
        return f"{days}d {hours}h"
    return f"{hours}h"


def _normalize_symbol(raw_symbol: str) -> str:
    return ''.join(ch for ch in str(raw_symbol or '').upper() if ch.isalnum())


def _build_cmc_normalized_lookup(cmc_by_symbol: dict[str, dict]) -> dict[str, list[tuple[str, dict]]]:
    lookup: dict[str, list[tuple[str, dict]]] = {}
    for symbol, payload in cmc_by_symbol.items():
        normalized = _normalize_symbol(symbol)
        if not normalized:
            continue
        lookup.setdefault(normalized, []).append((symbol, payload))
    return lookup


def _resolve_cmc_data(
    symbol: str,
    cmc_by_symbol: dict[str, dict],
    cmc_by_normalized_symbol: dict[str, list[tuple[str, dict]]],
    symbol_aliases: dict[str, str],
) -> tuple[dict | None, str | None, str]:
    symbol_upper = str(symbol or '').upper()
    if not symbol_upper:
        return None, None, 'missing'

    direct = cmc_by_symbol.get(symbol_upper)
    if direct:
        return direct, symbol_upper, 'direct'

    alias_target = symbol_aliases.get(symbol_upper)
    if alias_target:
        alias_direct = cmc_by_symbol.get(alias_target)
        if alias_direct:
            return alias_direct, alias_target, 'configured_alias'

        alias_normalized = _normalize_symbol(alias_target)
        alias_candidates = cmc_by_normalized_symbol.get(alias_normalized, [])
        if len(alias_candidates) == 1:
            matched_symbol, matched_payload = alias_candidates[0]
            return matched_payload, matched_symbol, 'configured_alias_normalized'

    normalized_symbol = _normalize_symbol(symbol_upper)
    normalized_candidates = cmc_by_normalized_symbol.get(normalized_symbol, [])
    if len(normalized_candidates) == 1:
        matched_symbol, matched_payload = normalized_candidates[0]
        return matched_payload, matched_symbol, 'normalized'

    return None, None, 'missing'


def _resolve_top_coin_data(
    symbol: str,
    *,
    top_coins_provider: str,
    cmc_by_symbol: dict[str, dict],
    cmc_by_normalized_symbol: dict[str, list[tuple[str, dict]]],
    cmc_symbol_aliases: dict[str, str],
    coingecko_id_aliases: dict[str, str],
    gecko: CoinGeckoClient,
) -> tuple[dict | None, str | None, str]:
    resolved_data, resolved_symbol, resolution_type = _resolve_cmc_data(
        symbol,
        cmc_by_symbol,
        cmc_by_normalized_symbol,
        cmc_symbol_aliases,
    )
    if resolved_data or top_coins_provider != 'coingecko':
        return resolved_data, resolved_symbol, resolution_type

    symbol_upper = str(symbol or '').upper()
    alias_gecko_id = coingecko_id_aliases.get(symbol_upper)
    if not alias_gecko_id:
        return None, None, 'missing'

    alias_snapshot = gecko.get_coin_market_snapshot(alias_gecko_id)
    if not alias_snapshot:
        return None, None, 'missing'

    alias_info = dict(alias_snapshot.get('info') or {})
    alias_info['symbol'] = symbol_upper
    alias_info.setdefault('source_url', f"https://www.coingecko.com/en/coins/{alias_gecko_id}")
    resolved_data = {
        'data': alias_snapshot.get('data', {}),
        'gains': alias_snapshot.get('gains', {}),
        'info': alias_info,
    }
    cmc_by_symbol[symbol_upper] = resolved_data
    return resolved_data, alias_gecko_id, 'coingecko_id_alias'


def _build_active_ranking_rows(
    final_results: list[dict],
    active_after_update: dict[str, dict],
) -> list[dict]:
    rows: list[dict] = []
    active_symbols = set(active_after_update.keys())

    active_rank = 0
    for coin in final_results:
        symbol = str(coin.get('symbol', '')).upper()
        if not symbol or symbol not in active_symbols:
            continue
        active_rank += 1

        after_state = active_after_update.get(symbol, {})
        current_price = float(coin.get('current_price', 0.0) or 0.0)
        gain_since_entry_pct = _pct_change(current_price, float(after_state.get('entry_price', 0.0) or 0.0))
        time_on_list = _format_time_on_list(after_state.get('entered_date'))

        rows.append(
            {
                'symbol': symbol,
                'active_rank': active_rank,
                'current_rank': coin.get('current_rank'),
                'rank_status': coin.get('rank_status'),
                'rank_delta': coin.get('rank_delta'),
                'health_score': coin.get('health_score'),
                'gain_since_entry_pct': gain_since_entry_pct,
                'time_on_list': time_on_list,
            }
        )

    return rows


def _format_signal_age_label(bars_ago: int, timeframe: str) -> str:
    normalized = str(timeframe or '1h').lower()
    hours_per_bar = {
        '1h': 1,
        '4h': 4,
        '1d': 24,
        'daily': 24,
    }.get(normalized, 1)

    if bars_ago <= 0:
        return f"current candle ({normalized})"

    approx_hours = bars_ago * hours_per_bar
    if approx_hours < 24:
        approx_label = f"~{approx_hours}h"
    else:
        approx_days = approx_hours / 24
        approx_label = f"~{approx_days:.1f}d" if approx_days % 1 else f"~{int(approx_days)}d"

    candle_label = 'candle' if bars_ago == 1 else 'candles'
    return f"{bars_ago} {candle_label} ago on {normalized} ({approx_label})"


def _attach_signal_age(coin: dict, loader: BacktestDataLoader) -> None:
    strategies = coin.get('backtest_top_strategies') or []
    if not strategies:
        return

    best_strategy = strategies[0]
    indicator = str(best_strategy.get('indicator', '')).strip()
    timeframe = str(best_strategy.get('timeframe', '1h')).strip().lower()
    params = best_strategy.get('params') or {}

    if not indicator or indicator == 'B&H':
        return

    loaded = loader.load(
        symbol=str(coin.get('symbol', '')).upper(),
        timeframe=timeframe,
        days=30,
        gecko_id=coin.get('gecko_id') or coin.get('cg_id'),
    )
    if loaded.frame is None or loaded.frame.empty:
        return

    try:
        buy_signals, sell_signals = generate_indicator_signals(indicator=indicator, frame=loaded.frame, params=params)
    except Exception as signal_error:
        app_logger.warning(f"⚠️ Signal age skipped for {coin.get('symbol', '?')}: {signal_error}")
        return

    recent_buy_index = buy_signals[buy_signals].index
    if len(recent_buy_index) == 0:
        return

    last_buy_ts = recent_buy_index[-1]
    location = loaded.frame.index.get_indexer([last_buy_ts])
    if len(location) == 0 or int(location[0]) < 0:
        return

    bars_ago = max(0, len(loaded.frame.index) - 1 - int(location[0]))
    last_sell_index = sell_signals[sell_signals].index
    signal_is_active = True
    if len(last_sell_index) > 0:
        signal_is_active = bool(last_sell_index[-1] < last_buy_ts)

    coin['signal_age_bars'] = bars_ago
    coin['signal_age_timeframe'] = timeframe
    coin['signal_age_label'] = _format_signal_age_label(bars_ago, timeframe)
    coin['signal_age_indicator'] = indicator
    coin['signal_age_active'] = signal_is_active


def _attach_volume_acceleration(coin: dict, loader: BacktestDataLoader) -> None:
    loaded = loader.load(
        symbol=str(coin.get('symbol', '')).upper(),
        timeframe='1h',
        days=10,
        gecko_id=coin.get('gecko_id') or coin.get('cg_id'),
    )
    if loaded.frame is None or loaded.frame.empty:
        return

    volume = loaded.frame['volume'].astype(float)
    if len(volume) < 48:
        return

    current_window = volume.iloc[-24:] if len(volume) >= 24 else volume
    previous_volume = volume.iloc[:-24]
    prior_window_count = min(7, len(previous_volume) // 24)
    if prior_window_count <= 0:
        return

    baseline_hours = previous_volume.iloc[-(prior_window_count * 24):]
    baseline_daily_totals = [
        float(baseline_hours.iloc[start:start + 24].sum())
        for start in range(0, len(baseline_hours), 24)
        if len(baseline_hours.iloc[start:start + 24]) == 24
    ]
    if not baseline_daily_totals:
        return

    current_24h_volume = float(current_window.sum())
    baseline_avg = float(sum(baseline_daily_totals) / len(baseline_daily_totals))
    if baseline_avg <= 0:
        return

    acceleration_pct = ((current_24h_volume - baseline_avg) / baseline_avg) * 100.0
    coin['volume_acceleration_pct'] = acceleration_pct
    coin['volume_acceleration_window_days'] = len(baseline_daily_totals)
    coin['volume_recent_24h'] = current_24h_volume
    coin['volume_baseline_24h'] = baseline_avg


def _attach_atr_score(coin: dict, loader: BacktestDataLoader) -> None:
    loaded = loader.load(
        symbol=str(coin.get('symbol', '')).upper(),
        timeframe='1d',
        days=60,
        gecko_id=coin.get('gecko_id') or coin.get('cg_id'),
    )
    if loaded.frame is None or loaded.frame.empty or len(loaded.frame.index) < 20:
        return

    high = [float(value) for value in loaded.frame['high'].tolist()]
    low = [float(value) for value in loaded.frame['low'].tolist()]
    close = [float(value) for value in loaded.frame['close'].tolist()]

    true_ranges = []
    for index in range(1, len(close)):
        tr = max(
            high[index] - low[index],
            abs(high[index] - close[index - 1]),
            abs(low[index] - close[index - 1]),
        )
        true_ranges.append(tr)

    if len(true_ranges) < 14:
        return

    atr14 = sum(true_ranges[-14:]) / 14.0
    last_close = close[-1]
    if last_close <= 0:
        return

    atr_pct = (atr14 / last_close) * 100.0
    atr_score = max(0.0, min(100.0, 100.0 - (atr_pct * 10.0)))
    coin['atr_pct'] = atr_pct
    coin['atr_score'] = atr_score


def _build_anomaly_messages(
    total_gain_qualified: int,
    missing_cg_count: int,
    no_ticker_count: int,
    cg_mapped_count: int,
    processed_ohlcv_count: int,
) -> list[str]:
    messages: list[str] = []

    if total_gain_qualified > 0:
        missing_cg_ratio = missing_cg_count / total_gain_qualified
        if missing_cg_ratio > settings.anomaly_max_missing_cg_ratio:
            messages.append(
                "High CoinGecko mapping miss ratio "
                f"({missing_cg_count}/{total_gain_qualified}, {missing_cg_ratio:.0%})"
            )

    if cg_mapped_count > 0:
        no_ticker_ratio = no_ticker_count / cg_mapped_count
        if no_ticker_ratio > settings.anomaly_max_no_ticker_ratio:
            messages.append(
                "High no-ticker ratio "
                f"({no_ticker_count}/{cg_mapped_count}, {no_ticker_ratio:.0%})"
            )

        ohlcv_success_ratio = processed_ohlcv_count / cg_mapped_count
        if ohlcv_success_ratio < settings.anomaly_min_ohlcv_success_ratio:
            messages.append(
                "Low OHLCV success ratio "
                f"({processed_ohlcv_count}/{cg_mapped_count}, {ohlcv_success_ratio:.0%})"
            )

    return messages


def _load_weekly_digest_state() -> dict:
    path = settings.weekly_digest_state_file
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_weekly_digest_state(payload: dict) -> None:
    path = settings.weekly_digest_state_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def _iso_week_key(moment: datetime) -> str:
    iso_year, iso_week, _ = moment.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _build_weekly_digest_message(history_db: HistoryDatabase, active_db: ActiveCoinsDatabase) -> str:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=7)
    cutoff_iso = cutoff.isoformat()
    cutoff_date = cutoff.date().isoformat()

    scans_cursor = history_db.execute(
        'SELECT COUNT(DISTINCT scan_date) FROM scan_history WHERE scan_date >= ?',
        (cutoff_iso,),
    )
    scans_count = int((scans_cursor.fetchone() or [0])[0] or 0)

    symbol_cursor = history_db.execute(
        'SELECT COUNT(DISTINCT coin_symbol) FROM scan_history WHERE scan_date >= ?',
        (cutoff_iso,),
    )
    unique_symbols = int((symbol_cursor.fetchone() or [0])[0] or 0)

    score_cursor = history_db.execute(
        'SELECT AVG(uniformity_score), MAX(uniformity_score) FROM scan_history WHERE scan_date >= ?',
        (cutoff_iso,),
    )
    score_row = score_cursor.fetchone() or [0, 0]
    avg_score = float(score_row[0] or 0.0)
    best_score = float(score_row[1] or 0.0)

    top_cursor = history_db.execute(
        '''
        SELECT coin_symbol, COUNT(*) AS appearances
        FROM scan_history
        WHERE scan_date >= ?
        GROUP BY coin_symbol
        ORDER BY appearances DESC, coin_symbol ASC
        LIMIT 5
        ''',
        (cutoff_iso,),
    )
    top_symbols = top_cursor.fetchall()

    active_entries_cursor = active_db.execute(
        'SELECT COUNT(*) FROM active_coins WHERE entered_date >= ?',
        (cutoff_date,),
    )
    new_entries_week = int((active_entries_cursor.fetchone() or [0])[0] or 0)

    recent_exits = active_db.get_recent_exits(days=7)
    exit_count = len(recent_exits)
    active_count = len(active_db.get_active())

    lines = [
        "📅 <b>Weekly Performance Digest</b>",
        f"Window: last 7 days (UTC)",
        f"Scans run: {scans_count}",
        f"Unique qualified symbols: {unique_symbols}",
        f"Average uniformity: {avg_score:.1f}",
        f"Best uniformity: {best_score:.1f}",
        f"New entries (active this week): {new_entries_week}",
        f"Exits: {exit_count}",
        f"Currently active: {active_count}",
    ]

    if top_symbols:
        lines.append("Top recurring symbols:")
        for symbol, appearances in top_symbols:
            lines.append(f"• {symbol}: {appearances} appearances")

    return "\n".join(lines)

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
        # STEP 1: Get top configured coins with gains from provider
        # ============================================================
        top_coins_provider = settings.top_coins_provider
        app_logger.info(
            f"\n📡 Fetching all coins with gains from {top_coins_provider.upper()} (limit={settings.top_coins_limit})..."
        )

        all_cmc_coins: list[dict] = []
        if top_coins_provider == 'coingecko':
            gecko_rows = gecko.get_top_coins_with_gains(limit=settings.top_coins_limit)
            if not gecko_rows:
                app_logger.error("❌ Failed to fetch coins from CoinGecko")
                tv_mapper.close()
                exchange_db.close()
                cg_mapper.close()
                return

            for index, row in enumerate(gecko_rows, start=1):
                symbol = str(row.get('symbol', '')).upper()
                if not symbol:
                    continue
                gecko_id = str(row.get('id', '')).strip()
                gains = {
                    '7d': float(row.get('price_change_percentage_7d_in_currency', 0) or 0),
                    '30d': float(row.get('price_change_percentage_30d_in_currency', 0) or 0),
                    '60d': 0.0,
                    '90d': 0.0,
                }
                info = {
                    'symbol': symbol,
                    'name': str(row.get('name', '')).strip(),
                    'slug': gecko_id,
                    'rank': int(row.get('market_cap_rank') or index),
                    'price': float(row.get('current_price', 0) or 0),
                    'volume_24h': float(row.get('total_volume', 0) or 0),
                    'source_url': f"https://www.coingecko.com/en/coins/{gecko_id}" if gecko_id else None,
                }
                all_cmc_coins.append(
                    {
                        'data': row,
                        'gains': gains,
                        'info': info,
                    }
                )
        else:
            cmc_rows = cmc.get_all_coins_with_gains(limit=settings.top_coins_limit)
            if not cmc_rows:
                app_logger.error("❌ Failed to fetch coins from CMC")
                tv_mapper.close()
                exchange_db.close()
                cg_mapper.close()
                return

            for row in cmc_rows:
                symbol = str(row.get('symbol', '')).upper()
                if not symbol:
                    continue
                all_cmc_coins.append(
                    {
                        'data': row,
                        'gains': cmc.extract_gains(row),
                        'info': cmc.extract_coin_data(row),
                    }
                )

        app_logger.info(f"✅ Got {len(all_cmc_coins)} coins with gain data")
        metrics.increment('coins_retrieved', len(all_cmc_coins))

        # Build lookup dict for quick access
        cmc_by_symbol = {}
        for coin in all_cmc_coins:
            info = coin.get('info') or {}
            symbol = str(info.get('symbol', '')).upper()
            if symbol:
                cmc_by_symbol[symbol] = {
                    'data': coin.get('data', {}),
                    'gains': coin.get('gains', {}),
                    'info': info,
                }

        cmc_by_normalized_symbol = _build_cmc_normalized_lookup(cmc_by_symbol)
        cmc_symbol_aliases = settings.cmc_symbol_aliases if top_coins_provider != 'coingecko' else {}
        coingecko_id_aliases = settings.coingecko_id_aliases if top_coins_provider == 'coingecko' else {}
        
        app_logger.info(f"📊 Built lookup for {len(cmc_by_symbol)} symbols")
        if cmc_symbol_aliases:
            app_logger.info(f"📎 CMC symbol aliases configured: {len(cmc_symbol_aliases)}")
        if coingecko_id_aliases:
            app_logger.info(f"📎 CoinGecko ID aliases configured: {len(coingecko_id_aliases)}")

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
        # STEP 3: Match with top-coin provider data and apply volume/gain filters
        # ============================================================
        app_logger.info(f"\n💰 FILTER 1: Applying volume and gain filters ({top_coins_provider.upper()})...")
        
        gain_qualified = []
        
        for symbol in all_symbols:
            # Filter out stablecoins per spec §5.5
            if symbol in STABLECOINS:
                app_logger.info(f"   ⏭️ {symbol}: Skipped (stablecoin)")
                continue
                
            cmc_data, resolved_cmc_symbol, resolution_type = _resolve_top_coin_data(
                symbol,
                top_coins_provider=top_coins_provider,
                cmc_by_symbol=cmc_by_symbol,
                cmc_by_normalized_symbol=cmc_by_normalized_symbol,
                cmc_symbol_aliases=cmc_symbol_aliases,
                coingecko_id_aliases=coingecko_id_aliases,
                gecko=gecko,
            )

            if cmc_data:
                if resolution_type != 'direct':
                    if top_coins_provider == 'coingecko' and resolution_type == 'coingecko_id_alias':
                        app_logger.info(
                            f"   ↪️ {symbol}: Matched CoinGecko id {resolved_cmc_symbol} via {resolution_type}"
                        )
                    else:
                        app_logger.info(
                            f"   ↪️ {symbol}: Matched CMC symbol {resolved_cmc_symbol} via {resolution_type}"
                        )
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
                            'cmc_symbol': resolved_cmc_symbol,
                            'name': info['name'],
                            'slug': info['slug'],
                            'source_url': info.get('source_url'),
                            'gains': gains,
                            'volume_24h': info['volume_24h'],
                            'current_price': float(info.get('price', 0) or 0),
                        }
                        gain_qualified.append(coin_info)
                        app_logger.info(f"   ✓ {symbol}: 7d:{gains['7d']:.1f}% 30d:{gains['30d']:.1f}% Vol:${info['volume_24h']:,.0f}")
                    else:
                        app_logger.info(f"   ❌ {symbol}: Gains too low (7d:{gains['7d']:.1f}% 30d:{gains['30d']:.1f}%)")
                else:
                    app_logger.info(f"   ❌ {symbol}: Volume too low (${info['volume_24h']:,.0f})")
            else:
                app_logger.info(
                    f"   ❌ {symbol}: Not found in {top_coins_provider.upper()} data"
                )
        
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

        symbols_for_listing_check = [str(coin.get('symbol', '')).upper() for coin in gain_qualified if coin.get('symbol')]
        exchange_listing_maps: dict[str, dict[str, bool]] = {}
        for exchange in settings.target_exchanges:
            exchange_listing_maps[exchange] = exchange_db.batch_check_listings(symbols_for_listing_check, exchange)

        for coin in gain_qualified:
            symbol = str(coin.get('symbol', '')).upper()
            coin['listed_on'] = [
                exchange
                for exchange in settings.target_exchanges
                if exchange_listing_maps.get(exchange, {}).get(symbol, False)
            ]

        # ============================================================
        # STEP 5: Get CoinGecko IDs for exchange volumes
        # ============================================================
        app_logger.info(f"\n🔍 Getting CoinGecko IDs for {len(gain_qualified)} coins...")
        
        coins_with_cg_ids = []
        coins_without_cg_ids = []
        
        for coin in gain_qualified:
            cg_id = cg_mapper.get_coin_id(coin['symbol'])
            if not cg_id and coin.get('cmc_symbol'):
                cg_id = cg_mapper.get_coin_id(str(coin['cmc_symbol']))
                if cg_id:
                    app_logger.info(
                        f"   ↪️ {coin['symbol']}: CoinGecko ID resolved via CMC symbol {coin['cmc_symbol']}"
                    )
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
        no_ticker_count = 0
        
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
                no_ticker_count += 1


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
        for coin in all_processed:
            compute_data_reliability(coin)

        anomaly_messages = _build_anomaly_messages(
            total_gain_qualified=len(gain_qualified),
            missing_cg_count=len(coins_without_cg_ids),
            no_ticker_count=no_ticker_count,
            cg_mapped_count=len(coins_with_cg_ids),
            processed_ohlcv_count=len(all_processed),
        )
        if anomaly_messages:
            app_logger.warning("⚠️ Anomaly detector triggered:")
            for message in anomaly_messages:
                app_logger.warning(f"   - {message}")

        # ============================================================
        # STEP 8: Apply uniformity filter
        # ============================================================
        app_logger.info(f"\n📐 FILTER 3: Applying uniformity filter (min: {settings.uniformity_min_score})...")
        
        uniformity_passed = []
        
        for coin in all_processed:
            if (
                'uniformity_score' in coin
                and coin['uniformity_score'] >= settings.uniformity_min_score
                and coin['total_gain'] > 0
            ):
                uniformity_passed.append(coin)
                app_logger.info(
                    f"   ✓ {coin['symbol']}: Score {coin['uniformity_score']:.1f}"
                )
            else:
                app_logger.info(
                    f"   ❌ {coin['symbol']}: Failed uniformity filter "
                    f"(score={float(coin.get('uniformity_score', 0.0) or 0.0):.1f})"
                )

        uniformity_passed_symbols = {c['symbol'] for c in uniformity_passed}

        # ============================================================
        # STEP 9: Sort and process final results
        # ============================================================
        final_results = sorted(
            uniformity_passed,
            key=lambda x: (
                -float(x.get('uniformity_score', 0.0) or 0.0),
                -float((x.get('gains') or {}).get('30d', 0.0) or 0.0),
                str(x.get('symbol', '')).upper(),
            ),
        )
        _attach_rank_movement(final_results, history_db.get_latest_rank_map())
        regime = detect_regime(all_cmc_coins, gain_qualified, final_results)
        for coin in final_results:
            coin['market_regime'] = regime.get('regime')

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

        recent_exits_30d = active_db.get_recent_exits(days=30)
        notification_loader = BacktestDataLoader(cache=cache, max_cache_age_hours=settings.cache_price_hours)
        for coin in final_results:
            coin.update(compute_reentry_quality(str(coin.get('symbol', '')), recent_exits_30d))
            _attach_atr_score(coin, notification_loader)
            _attach_signal_age(coin, notification_loader)
            _attach_volume_acceleration(coin, notification_loader)
            compute_health_score(coin)

        final_results = sorted(
            final_results,
            key=lambda x: (
                -float(x.get('health_score', 0.0) or 0.0),
                -float(x.get('uniformity_score', 0.0) or 0.0),
                -float((x.get('gains') or {}).get('30d', 0.0) or 0.0),
                str(x.get('symbol', '')).upper(),
            ),
        )
        _attach_rank_movement(final_results, history_db.get_latest_rank_map())
        
        # Check entries/exits
        app_logger.info("\n🔄 Checking for entries/exits...")
        active_before_update = active_db.get_active()
        entered, exited, blocked_by_cooldown = active_db.get_entered_exited(
            final_results,
            cooldown_hours=settings.alert_cooldown_hours,
        )
        app_logger.info(
            f"   New entries: {len(entered)}, Exits: {len(exited)}, "
            f"Blocked by cooldown: {len(blocked_by_cooldown)}"
        )
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

            for coin in entered:
                for enriched_coin in final_results:
                    if str(enriched_coin.get('symbol', '')).upper() == str(coin.get('symbol', '')).upper():
                        coin.update(enriched_coin)
                        break

        # Attach precise exit reasons based on first failed pipeline stage
        for coin in exited:
            symbol = coin['symbol']
            coin['exited_at'] = datetime.now(timezone.utc).isoformat()
            coin['cooldown_until'] = (datetime.now(timezone.utc) + timedelta(hours=settings.alert_cooldown_hours)).isoformat()

            if symbol in STABLECOINS:
                coin['exit_reason'] = "Filtered as stablecoin"
                continue

            if symbol not in all_symbols_set:
                coin['exit_reason'] = "No longer listed on target exchanges"
                continue

            cmc_data, _, _ = _resolve_top_coin_data(
                symbol,
                top_coins_provider=top_coins_provider,
                cmc_by_symbol=cmc_by_symbol,
                cmc_by_normalized_symbol=cmc_by_normalized_symbol,
                cmc_symbol_aliases=cmc_symbol_aliases,
                coingecko_id_aliases=coingecko_id_aliases,
                gecko=gecko,
            )
            if not cmc_data:
                if top_coins_provider == 'coingecko':
                    coin['exit_reason'] = "Missing from current CoinGecko top-coin provider snapshot"
                else:
                    coin['exit_reason'] = "Missing from current CoinMarketCap snapshot"
                continue

            gains = cmc_data['gains']
            info = cmc_data['info']
            coin['gain_7d'] = float(gains.get('7d', 0) or 0)
            coin['gain_30d'] = float(gains.get('30d', 0) or 0)
            coin['volume_24h'] = float(info.get('volume_24h', 0) or 0)

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
            coin['uniformity_score'] = float(processed_coin.get('uniformity_score', 0) or 0)
            coin['health_score'] = processed_coin.get('health_score')
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

        for coin in exited:
            active_db.register_exit(
                coin['symbol'],
                reason=str(coin.get('exit_reason', 'No longer qualified')),
                cooldown_hours=settings.alert_cooldown_hours,
            )

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

        active_after_update = active_db.get_active()
        watchlist_rows = build_watchlist(
            all_processed=all_processed,
            final_symbols={str(coin.get('symbol', '')).upper() for coin in final_results},
            uniformity_min_score=settings.uniformity_min_score,
            score_buffer=settings.watchlist_score_buffer,
        ) if settings.watchlist_enabled else []
        insights_payload = update_scanner_insights(
            settings.scanner_insights_file,
            final_results=final_results,
            all_processed=all_processed,
            gain_qualified=gain_qualified,
            all_cmc_coins=all_cmc_coins,
            entered=entered,
            exited=exited,
            active_before_update=active_before_update,
            active_after_update=active_after_update,
            blocked_by_cooldown=blocked_by_cooldown,
            regime=regime,
            watchlist=watchlist_rows,
            current_metrics_summary=metrics.get_summary(),
            portfolio_starting_capital=settings.portfolio_sim_starting_capital,
        )
        drift_summary = insights_payload.get('benchmark_drift', {}) or {}
        app_logger.info(
            "🧭 Insights updated: "
            f"regime={regime.get('regime')}, watchlist={len(watchlist_rows)}, "
            f"drift={drift_summary.get('status', 'stable')}"
        )
        
        # ============================================================
        # STEP 10: Send Telegram notifications with chart images
        # ============================================================
        if telegram and entered and settings.entry_notifications:
            with timed_block('notifications'):
                app_logger.info(f"\n📱 Sending entry notifications for {len(entered)} new coins...")
                
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
                message = MessageFormatter.format_exit(coin)
                exit_image = build_exit_notification_image(coin, settings.db_paths['scanner'])
                if exit_image:
                    telegram.send_photo(io.BytesIO(exit_image), caption=message)
                else:
                    telegram.send_message(message)
                metrics.increment('notifications_sent')

        if telegram and settings.anomaly_alerts_enabled and anomaly_messages:
            anomaly_text = "⚠️ <b>Scanner Anomaly Detector</b>\n" + "\n".join(f"• {m}" for m in anomaly_messages)
            telegram.send_message(anomaly_text)
            metrics.increment('notifications_sent')

        if telegram and settings.weekly_digest_enabled:
            now_utc = datetime.now(timezone.utc)
            state = _load_weekly_digest_state()
            current_week_key = _iso_week_key(now_utc)
            already_sent = str(state.get('last_sent_week', '')) == current_week_key
            is_due_slot = (
                now_utc.weekday() == settings.weekly_digest_weekday_utc
                and now_utc.hour >= settings.weekly_digest_hour_utc
            )
            if is_due_slot and not already_sent:
                digest_message = _build_weekly_digest_message(history_db, active_db)
                digest_message_id = telegram.send_message(digest_message)
                if digest_message_id:
                    _save_weekly_digest_state(
                        {
                            'last_sent_week': current_week_key,
                            'last_sent_at': now_utc.isoformat(),
                            'last_message_id': digest_message_id,
                        }
                    )
                    metrics.increment('notifications_sent')

        if telegram and (entered or exited):
            app_logger.info("\n📱 Sending scanner event summary notification...")
            active_ranking_rows = _build_active_ranking_rows(
                final_results,
                active_after_update,
            )
            sent_summary_count = 0
            summary_image = build_hourly_summary_image(
                active_rows=active_ranking_rows,
                watchlist_rows=watchlist_rows,
                regime=regime,
                drift=drift_summary,
            )
            if summary_image:
                summary_msg_id = telegram.send_photo(
                    io.BytesIO(summary_image),
                    caption=MessageFormatter.format_summary_caption(
                        regime=regime,
                        drift=drift_summary,
                        active_count=len(active_ranking_rows),
                        watchlist_count=len(watchlist_rows),
                    ),
                )
                if summary_msg_id:
                    sent_summary_count = 1
                    metrics.increment('notifications_sent')

            if sent_summary_count == 0:
                fallback_summary = (
                    "🖼️ <b>Scanner Event Dashboard</b>\n"
                    f"Entries: {len(entered)} | Exits: {len(exited)} | Cooldown blocked: {len(blocked_by_cooldown)}\n"
                    f"Active: {len(active_ranking_rows)} | Watchlist: {len(watchlist_rows)}"
                )
                fallback_msg_id = telegram.send_message(fallback_summary)
                if fallback_msg_id:
                    sent_summary_count = 1
                    metrics.increment('notifications_sent')
            app_logger.info(
                "📌 EVENT_SUMMARY_SENT "
                f"messages={sent_summary_count}/1 "
                f"active_coins={len(active_ranking_rows)}"
            )

        if not telegram and (entered or exited):
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