#!/usr/bin/env python3
"""Linear Trend Spotter - Scans ALL exchange-listed coins"""
import os
import sys
import json
import io
from html import escape as html_escape
from dataclasses import replace
from datetime import datetime, timezone, timedelta

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from config.constants import STABLECOINS
from processors.uniformity_filter import UniformityFilter
from notifications.formatter import MessageFormatter
from notifications.image_renderer import (
    build_combined_notification_image,
    build_exit_notification_image,
    build_hourly_summary_image,
)
from backtesting.data_loader import BacktestDataLoader
from backtesting.runner import run_backtests_for_final_results
from backtesting.params import runner_params_from_settings
from backtesting.report import notification_rows_for_symbol
from utils.insights import (
    compute_data_reliability,
    compute_health_score,
    compute_reentry_quality,
    update_scanner_insights,
)
from utils.metrics import metrics, timed_block
from utils.runtime_hygiene import run_artifact_hygiene, update_exit_reason_analytics
from utils.scan_artifacts import (
    write_public_qualified_snapshot,
    write_scan_heartbeat,
)
from utils.scan_costs import read_last_completed_coingecko_http_total, write_scan_costs_file
from utils.watchlist_export import compute_watchlist_rows, write_watchlist_exports
from utils.portfolio_multi import write_multi_portfolio_simulation
from utils.alert_backtest_report import write_alert_backtest_report
from utils.quiet_hours import is_within_utc_quiet_window
from utils.still_qualifying_notify import sync_still_qualifying_scan_message
from utils.logger import app_logger, maybe_install_structured_json_handler
from scanner.active_ranking import build_active_ranking_rows
from scanner.anomaly_alerts import build_anomaly_messages
from scanner.coin_enrichment import (
    attach_rank_movement,
    attach_signal_age,
    attach_volume_acceleration,
)
from scanner.market_processing import aggregate_daily_bars_from_hourly
from scanner.quiet_hours import telegram_quiet_active
from scanner.regime_filter import evaluate_regime_gate
from scanner.top_coin_resolution import ensure_cmc_notify_urls, resolve_top_coin_data
from scanner.weekly_digest import (
    build_weekly_digest_message,
    iso_week_key,
    load_weekly_digest_state,
    save_weekly_digest_state,
)
from scanner.web_push_notify import maybe_notify_web_push_scan
from scanner.runtime_init import initialize_runtime_components
from scanner.top_coins_stage import fetch_top_coins_dataset
from scanner.exchange_universe import load_exchange_symbol_universe
from scanner.coingecko_alias_prefetch import prefetch_alias_markets_by_gecko_id
from scanner.gain_volume_filter import apply_gain_volume_filter
from scanner.listings_and_volumes import (
    attach_coin_gecko_ids_and_learn,
    attach_target_exchange_listings,
    hydrate_exchange_volumes_from_coingecko,
)

# Import exchange database
from exchange_data.exchange_fetcher import ExchangeFetcher


def run_scanner():
    """Main orchestration function"""
    maybe_install_structured_json_handler()
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
        scan_started_at = datetime.now(timezone.utc)
        # Initialize components
        with timed_block('initialization'):
            runtime = initialize_runtime_components(settings)
            history_db = runtime["history_db"]
            active_db = runtime["active_db"]
            cache = runtime["cache"]
            exchange_db = runtime["exchange_db"]
            tv_mapper = runtime["tv_mapper"]
            cmc = runtime["cmc"]
            gecko = runtime["gecko"]
            history_fallback = runtime["history_fallback"]
            cg_mapper = runtime["cg_mapper"]
            telegram = runtime["telegram"]
            cmc_slug_resolver = runtime["cmc_slug_resolver"]
            exchange_db_path = settings.db_paths["exchanges"]
        
        # ============================================================
        # STEP 1: Get top configured coins with gains from provider
        # ============================================================
        top_coins_provider = settings.top_coins_provider
        app_logger.info(
            f"\n📡 Fetching all coins with gains from {top_coins_provider.upper()} (limit={settings.top_coins_limit})..."
        )

        top_dataset = fetch_top_coins_dataset(
            top_coins_provider=top_coins_provider,
            top_coins_limit=settings.top_coins_limit,
            cmc_symbol_aliases=settings.cmc_symbol_aliases if top_coins_provider != "coingecko" else {},
            coingecko_id_aliases=settings.coingecko_id_aliases if top_coins_provider == "coingecko" else {},
            gecko=gecko,
            cmc=cmc,
            app_logger=app_logger,
            metrics=metrics,
        )
        if top_dataset is None:
            tv_mapper.close()
            exchange_db.close()
            cg_mapper.close()
            return

        all_cmc_coins = top_dataset.all_cmc_coins
        cmc_by_symbol = top_dataset.cmc_by_symbol
        cmc_by_normalized_symbol = top_dataset.cmc_by_normalized_symbol
        cmc_symbol_aliases = top_dataset.cmc_symbol_aliases
        coingecko_id_aliases = top_dataset.coingecko_id_aliases

        app_logger.info(f"📊 Built lookup for {len(cmc_by_symbol)} symbols")
        if cmc_symbol_aliases:
            app_logger.info(f"📎 CMC symbol aliases configured: {len(cmc_symbol_aliases)}")
        if coingecko_id_aliases:
            app_logger.info(f"📎 CoinGecko ID aliases configured: {len(coingecko_id_aliases)}")

        # ============================================================
        # STEP 2: Get ALL symbols from exchange listings (no limit!)
        # ============================================================
        app_logger.info("\n🔍 Getting ALL token symbols from exchange listings...")

        all_symbols, all_symbols_set = load_exchange_symbol_universe(
            exchange_db_path,
            exchange_db,
            ExchangeFetcher,
            app_logger,
        )

        alias_markets_by_id = prefetch_alias_markets_by_gecko_id(
            top_coins_provider=top_coins_provider,
            coingecko_id_aliases=coingecko_id_aliases,
            all_symbols=all_symbols,
            gecko=gecko,
            app_logger=app_logger,
        )

        # ============================================================
        # STEP 3: Match with top-coin provider data and apply volume/gain filters
        # ============================================================
        gain_qualified = apply_gain_volume_filter(
            all_symbols,
            top_coins_provider=top_coins_provider,
            min_volume=float(settings.min_volume),
            gain_filter_min_7d_percent=float(settings.gain_filter_min_7d_percent),
            gain_filter_min_30d_percent=float(settings.gain_filter_min_30d_percent),
            cmc_by_symbol=cmc_by_symbol,
            cmc_by_normalized_symbol=cmc_by_normalized_symbol,
            cmc_symbol_aliases=cmc_symbol_aliases,
            coingecko_id_aliases=coingecko_id_aliases,
            gecko=gecko,
            alias_markets_by_id=alias_markets_by_id,
            cmc_slug_resolver=cmc_slug_resolver,
            app_logger=app_logger,
            metrics=metrics,
        )

        gain_qualified_symbols = {c["symbol"] for c in gain_qualified}

        if not gain_qualified:
            app_logger.warning("No coins passed gain filter")
            tv_mapper.close()
            exchange_db.close()
            cg_mapper.close()
            return

        # ============================================================
        # STEP 4–6: Listings, CoinGecko IDs, exchange volumes
        # ============================================================
        attach_target_exchange_listings(
            gain_qualified,
            exchange_db=exchange_db,
            target_exchanges=tuple(settings.target_exchanges),
            app_logger=app_logger,
        )

        coins_with_cg_ids, coins_without_cg_ids = attach_coin_gecko_ids_and_learn(
            gain_qualified,
            top_coins_provider=top_coins_provider,
            cg_mapper=cg_mapper,
            cmc_slug_resolver=cmc_slug_resolver,
            app_logger=app_logger,
        )

        coins_with_cg_ids_symbols = {c["symbol"] for c in coins_with_cg_ids}

        if not coins_with_cg_ids:
            app_logger.warning("No coins with CoinGecko IDs")
            tv_mapper.close()
            exchange_db.close()
            cg_mapper.close()
            return

        no_ticker_count = hydrate_exchange_volumes_from_coingecko(
            coins_with_cg_ids,
            cache=cache,
            gecko=gecko,
            target_exchanges=tuple(settings.target_exchanges),
            app_logger=app_logger,
        )

        # ============================================================
        # STEP 7: Calculate uniformity scores
        # ============================================================
        app_logger.info("\n📐 FILTER 2: Calculating uniformity scores...")
        
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
                found_cmc, cached_cmc_rows = cache.get_ohlcv_rows(
                    'cmc', coin['symbol'], '1h', max_age_hours=settings.cache_price_hours
                )
                if found_cmc and cached_cmc_rows:
                    hourly_rows = cached_cmc_rows
                    ohlcv_source = 'cmc_cache'
                else:
                    cmc_hourly = history_fallback.get_cmc_hourly_ohlcv(coin['symbol'], days=max(30, uniformity_days))
                    if cmc_hourly:
                        cache.cache_ohlcv_rows('cmc', coin['symbol'], '1h', cmc_hourly, source='cmc_api')
                        hourly_rows = cmc_hourly
                        ohlcv_source = 'cmc_api'

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

        anomaly_messages = build_anomaly_messages(
            total_gain_qualified=len(gain_qualified),
            missing_cg_count=len(coins_without_cg_ids),
            no_ticker_count=no_ticker_count,
            cg_mapped_count=len(coins_with_cg_ids),
            processed_ohlcv_count=len(all_processed),
            max_missing_cg_ratio=settings.anomaly_max_missing_cg_ratio,
            max_no_ticker_ratio=settings.anomaly_max_no_ticker_ratio,
            min_ohlcv_success_ratio=settings.anomaly_min_ohlcv_success_ratio,
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

        if settings.regime_filter_enabled:
            regime_ok, regime_reason, regime_ctx = evaluate_regime_gate(
                all_cmc_coins,
                btc_min_30d_gain=settings.regime_filter_btc_min_30d_gain,
                btc_max_abs_7d_gain=settings.regime_filter_btc_max_abs_7d_gain,
            )
            if regime_ok:
                if regime_ctx:
                    app_logger.info(
                        "🌦️ Regime filter pass: btc_7d=%.2f%% btc_30d=%.2f%%",
                        float(regime_ctx.get("btc_7d", 0.0)),
                        float(regime_ctx.get("btc_30d", 0.0)),
                    )
                else:
                    app_logger.info("🌦️ Regime filter pass: %s", regime_reason)
            else:
                app_logger.warning("🌦️ Regime filter blocked qualification: %s", regime_reason)
                uniformity_passed = []
                uniformity_passed_symbols = set()

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
        attach_rank_movement(final_results, history_db.get_latest_rank_map())


        # ============================================================
        # STEP 9.1: Optional backtesting run (feature-flagged)
        # ============================================================
        backtest_summary = None
        skip_backtest = False
        skip_reason = ""
        if settings.degrade_skip_backtest_enabled:
            ge = settings.degrade_prior_cg_http_skip_ge
            if ge <= 0:
                skip_backtest = True
                skip_reason = (
                    "DEGRADE_SKIP_BACKTEST_ENABLED with DEGRADE_PRIOR_CG_HTTP_SKIP_GE<=0 "
                    "(skip every run; emergency ops only)"
                )
            else:
                prior = read_last_completed_coingecko_http_total(settings.metrics_file)
                if prior is not None and prior >= ge:
                    skip_backtest = True
                    skip_reason = (
                        f"prior scan coingecko_http_total={prior} >= DEGRADE_PRIOR_CG_HTTP_SKIP_GE={ge}"
                    )
                elif prior is None:
                    app_logger.info(
                        "   ℹ️ Degrade skip enabled but no prior metrics.json entry; running backtests"
                    )

        if skip_backtest:
            app_logger.warning("\n⏭️ Skipping backtests (J4 degrade): %s", skip_reason)
            if telegram:
                try:
                    telegram.send_message(
                        "<b>Degraded scan</b>\nBacktests skipped this run:\n"
                        + html_escape(skip_reason[:500])
                    )
                except Exception as degrade_notify_err:
                    app_logger.warning("   ⚠️ Could not send degrade notice: %s", degrade_notify_err)

        if settings.backtest_enabled and not skip_backtest:
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

        if settings.backtest_ab_shadow_enabled and settings.backtest_enabled and not skip_backtest and final_results:
            shadow_subset = final_results[: max(1, int(settings.backtest_ab_shadow_max_coins))]
            app_logger.info(
                "\n🧪 Running shadow A/B backtest (L4): subset=%s max_param_combos=%s",
                len(shadow_subset),
                int(settings.backtest_ab_shadow_max_param_combos),
            )
            try:
                base_params = runner_params_from_settings()
                shadow_params = replace(
                    base_params,
                    backtest_resume_enabled=False,
                    backtest_max_coins_per_run=len(shadow_subset),
                    backtest_max_param_combos=int(settings.backtest_ab_shadow_max_param_combos),
                    backtest_trailing_stop_min=int(settings.backtest_ab_shadow_trailing_stop_min),
                    backtest_trailing_stop_max=int(settings.backtest_ab_shadow_trailing_stop_max),
                    backtest_trailing_stop_step=int(settings.backtest_ab_shadow_trailing_stop_step),
                    backtest_checkpoint_file=settings.backtest_ab_shadow_checkpoint_file,
                    backtest_telemetry_file=settings.backtest_ab_shadow_telemetry_file,
                )
                shadow_summary = run_backtests_for_final_results(
                    shadow_subset,
                    output_path=settings.backtest_ab_shadow_results_file,
                    params=shadow_params,
                )
                app_logger.info(
                    "   ✅ Shadow A/B complete (logs-only): eligible=%s processed=%s failed=%s rows=%s",
                    shadow_summary.get("coins_eligible", 0),
                    shadow_summary.get("coins_processed", 0),
                    shadow_summary.get("coins_failed", 0),
                    shadow_summary.get("rows_generated", 0),
                )
            except Exception as shadow_error:
                app_logger.warning("   ⚠️ Shadow A/B backtest failed (ignored): %s", shadow_error)

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
            attach_signal_age(coin, notification_loader, app_logger)
            attach_volume_acceleration(coin, notification_loader)
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
        attach_rank_movement(final_results, history_db.get_latest_rank_map())
        
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
                    for enriched_coin in final_results:
                        if str(enriched_coin.get('symbol', '')).upper() == str(coin.get('symbol', '')).upper():
                            coin.update(enriched_coin)

                for coin in entered:
                    if coin.get('backtest_top_strategies') and coin.get('backtest_buy_hold'):
                        continue
                    symbol = coin.get('symbol', '')
                    if not symbol:
                        continue
                    if fallback_summary:
                        details = notification_rows_for_symbol(fallback_summary, symbol, top_n=5)
                        coin['backtest_top_strategies'] = details.get('top_strategies', [])
                        coin['backtest_buy_hold'] = details.get('buy_hold')

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

            cmc_data, _, _ = resolve_top_coin_data(
                symbol,
                top_coins_provider=top_coins_provider,
                cmc_by_symbol=cmc_by_symbol,
                cmc_by_normalized_symbol=cmc_by_normalized_symbol,
                cmc_symbol_aliases=cmc_symbol_aliases,
                coingecko_id_aliases=coingecko_id_aliases,
                gecko=gecko,
                alias_markets_by_id=alias_markets_by_id,
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

            gain_7d = float(gains.get('7d', 0) or 0)
            gain_30d = float(gains.get('30d', 0) or 0)
            min7 = float(settings.gain_filter_min_7d_percent)
            min30 = float(settings.gain_filter_min_30d_percent)
            if gain_7d < min7:
                coin['exit_reason'] = f"7d gain below threshold ({gain_7d:.1f}% < {min7:g}%)"
                continue
            if gain_30d <= min30:
                coin['exit_reason'] = f"30d gain below threshold ({gain_30d:.1f}% ≤ {min30:g}%)"
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
        final_symbol_set = {str(c.get("symbol", "")).upper() for c in final_results if c.get("symbol")}
        watchlist_rows = compute_watchlist_rows(
            all_processed,
            final_symbol_set,
            uniformity_min_score=settings.uniformity_min_score,
            watchlist_score_buffer=settings.watchlist_score_buffer,
        )
        if settings.watchlist_export_enabled:
            try:
                write_watchlist_exports(
                    settings.base_dir,
                    settings.watchlist_export_csv_file,
                    settings.watchlist_export_json_file,
                    watchlist_rows,
                )
                app_logger.info("📋 Watchlist export written (%s row(s))", len(watchlist_rows))
            except Exception as export_err:
                app_logger.warning("⚠️ Watchlist export failed: %s", export_err)
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

            current_metrics_summary=metrics.get_summary(),
            portfolio_starting_capital=settings.portfolio_sim_starting_capital,
        )
        app_logger.info("🧭 Insights updated")
        if settings.portfolio_multi_sim_enabled:
            try:
                write_multi_portfolio_simulation(
                    path=settings.portfolio_multi_sim_file,
                    insights_payload=insights_payload,
                    capitals=settings.portfolio_multi_sim_capitals,
                )
                app_logger.info("🧮 Multi-portfolio simulation updated")
            except Exception as multi_sim_err:
                app_logger.warning("⚠️ Multi-portfolio simulation update failed: %s", multi_sim_err)
        if settings.alert_backtest_report_enabled:
            try:
                write_alert_backtest_report(
                    path=settings.alert_backtest_report_file,
                    final_results=final_results,
                    active_after_update=active_after_update,
                    exited=exited,
                    top_n=settings.alert_backtest_report_top_n,
                )
                app_logger.info("📘 Alert backtest report updated")
            except Exception as report_err:
                app_logger.warning("⚠️ Alert backtest report update failed: %s", report_err)
        
        # ============================================================
        # STEP 10: Send Telegram notifications with chart images
        # ============================================================
        quiet = telegram_quiet_active(
            quiet_hours_enabled=settings.quiet_hours_enabled,
            quiet_hours_start_hour_utc=settings.quiet_hours_start_hour_utc,
            quiet_hours_end_hour_utc=settings.quiet_hours_end_hour_utc,
            is_within_utc_quiet_window=is_within_utc_quiet_window,
        )
        if telegram and entered and settings.entry_notifications:
            with timed_block('notifications'):
                app_logger.info(f"\n📱 Sending entry notifications for {len(entered)} new coins...")
                
                for coin in entered:
                    app_logger.info(f"   🟢 {coin['symbol']}")
                    ensure_cmc_notify_urls(coin, cmc_slug_resolver)

                    # Get chart image from Chart-IMG (external service)
                    caption = MessageFormatter.format_entry(coin)
                    entry_markup = telegram.coin_link_reply_markup(coin)
                    
                    combined_image = None
                    try:
                        combined_image = build_combined_notification_image(coin, settings.db_paths['scanner'])
                    except Exception as e:
                        app_logger.error(f"      ❌ Failed to build combined image for {coin['symbol']}: {e}")

                    if combined_image:
                        img_data = io.BytesIO(combined_image)
                        message_id = telegram.send_photo(
                            img_data,
                            caption=caption,
                            reply_markup=entry_markup,
                        )
                        if message_id:
                            app_logger.info("      📤 Sent combined image notification")
                        else:
                            app_logger.error("      ❌ Failed to send combined image notification, falling back to text")
                            telegram.send_message(caption, reply_markup=entry_markup)

                    else:
                        message_id = telegram.send_message(caption, reply_markup=entry_markup)
                        if message_id:
                            app_logger.info("      📤 Sent text-only notification")
                        else:
                            app_logger.error("      ❌ Failed to send text-only notification")
                    
                    metrics.increment('notifications_sent')
        
        if telegram and exited and settings.exit_notifications:
            app_logger.info(f"\n📱 Sending exit notifications for {len(exited)} coins...")
            for coin in exited:
                app_logger.info(f"   🔴 Exit: {coin['symbol']}")
                ensure_cmc_notify_urls(coin, cmc_slug_resolver)
                message = MessageFormatter.format_exit(coin)
                exit_markup = telegram.coin_link_reply_markup(coin)
                try:
                    exit_image = build_exit_notification_image(coin, settings.db_paths['scanner'])
                except Exception as e:
                    app_logger.error(f"      ❌ Failed to build exit image for {coin['symbol']}: {e}")
                    exit_image = None

                if exit_image:
                    sent = telegram.send_photo(
                        io.BytesIO(exit_image),
                        caption=message,
                        reply_markup=exit_markup,
                    )
                    if not sent:
                        app_logger.warning(f"      ⚠️ Failed to send exit image for {coin['symbol']}, falling back to text")
                        telegram.send_message(message, reply_markup=exit_markup)
                else:
                    telegram.send_message(message, reply_markup=exit_markup)

                metrics.increment('notifications_sent')

        if (
            telegram
            and settings.anomaly_alerts_enabled
            and anomaly_messages
            and not (quiet and settings.quiet_hours_suppress_anomaly)
        ):
            anomaly_text = "⚠️ <b>Scanner Anomaly Detector</b>\n" + "\n".join(f"• {m}" for m in anomaly_messages)
            telegram.send_message(anomaly_text)
            metrics.increment('notifications_sent')

        if (
            telegram
            and settings.weekly_digest_enabled
            and not (quiet and settings.quiet_hours_suppress_weekly_digest)
        ):
            now_utc = datetime.now(timezone.utc)
            state = load_weekly_digest_state()
            current_week_key = iso_week_key(now_utc)
            already_sent = str(state.get('last_sent_week', '')) == current_week_key
            is_due_slot = (
                now_utc.weekday() == settings.weekly_digest_weekday_utc
                and now_utc.hour >= settings.weekly_digest_hour_utc
            )
            if is_due_slot and not already_sent:
                digest_message = build_weekly_digest_message(history_db, active_db)
                digest_message_id = telegram.send_message(digest_message)
                if digest_message_id:
                    save_weekly_digest_state(
                        {
                            'last_sent_week': current_week_key,
                            'last_sent_at': now_utc.isoformat(),
                            'last_message_id': digest_message_id,
                        }
                    )
                    metrics.increment('notifications_sent')

        if (
            telegram
            and (entered or exited)
            and not (quiet and settings.quiet_hours_suppress_event_summary)
        ):
            app_logger.info("\n📱 Sending scanner event summary notification...")
            active_ranking_rows = build_active_ranking_rows(
                final_results,
                active_after_update,
            )
            sent_summary_count = 0
            summary_image = build_hourly_summary_image(
                active_rows=active_ranking_rows,
            )
            if summary_image:
                summary_msg_id = telegram.send_photo(
                    io.BytesIO(summary_image),
                    caption=MessageFormatter.format_summary_caption(
                        active_count=len(active_ranking_rows),
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

        if telegram and sync_still_qualifying_scan_message(
            telegram,
            state_path=settings.still_qualifying_state_path,
            final_results=final_results,
            entered_len=len(entered),
            exited_len=len(exited),
            enabled=settings.still_qualifying_edit_enabled,
            no_change_notifications=settings.no_change_notifications,
            quiet_suppress=quiet and settings.quiet_hours_suppress_still_qualifying,
        ):
            metrics.increment('notifications_sent')

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
        app_logger.info("\n📊 Cache Summary:")
        app_logger.info(f"   Coin list: {stats['total_coins']} coins")
        app_logger.info(f"   Last updated: {stats['last_update'][:16] if stats['last_update'] != 'Never' else 'Never'}")
        
        metrics.save(settings.metrics_file)

        if settings.scan_costs_enabled:
            try:
                write_scan_costs_file(
                    settings.DATA_DIR,
                    settings.scan_costs_file,
                    metrics.get_summary(),
                )
                app_logger.info("📉 Scan costs artifact written (%s)", settings.scan_costs_file)
            except Exception as costs_err:
                app_logger.warning("⚠️ Scan costs write failed: %s", costs_err)

        if settings.scan_heartbeat_enabled:
            try:
                write_scan_heartbeat(
                    settings.DATA_DIR,
                    filename=settings.scan_heartbeat_file,
                    status="ok",
                    started_at=scan_started_at,
                    finished_at=datetime.now(timezone.utc),
                    extra={
                        "gain_qualified": len(gain_qualified),
                        "final_results": len(final_results),
                        "entered": len(entered),
                        "exited": len(exited),
                    },
                )
                app_logger.info("💓 Scan heartbeat written")
            except Exception as hb_err:
                app_logger.warning("⚠️ Scan heartbeat failed: %s", hb_err)

        if settings.public_qualified_snapshot_enabled and final_results:
            try:
                finished_at = datetime.now(timezone.utc)
                wall_s = max(0.0, (finished_at - scan_started_at).total_seconds())
                err_map = metrics.get_summary().get("errors") or {}
                err_total = 0
                for v in err_map.values():
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        continue
                    err_total += int(v)
                write_public_qualified_snapshot(
                    settings.DATA_DIR,
                    settings.public_qualified_snapshot_file,
                    final_results,
                    field_set=settings.public_qualified_snapshot_field_set,
                    scan_interval_seconds=settings.scan_interval_seconds,
                    scan_health={
                        "scan_duration_s": round(wall_s, 2),
                        "coins_evaluated": len(all_symbols),
                        "errors_count": int(err_total),
                    },
                )
                app_logger.info("📤 Public qualified snapshot written")
            except Exception as snap_err:
                app_logger.warning("⚠️ Public snapshot failed: %s", snap_err)

        maybe_notify_web_push_scan()

        app_logger.info("\n✅ Scan complete")
        
        tv_mapper.close()
        exchange_db.close()
        cg_mapper.close()
        cache.close()
        
    except Exception as e:
        app_logger.error(f"Scan failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    run_scanner()