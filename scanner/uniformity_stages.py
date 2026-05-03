"""OHLCV uniformity scoring, anomaly summary, and uniformity/regime gate — Milestone I2."""

from __future__ import annotations

from typing import Any

from processors.uniformity_filter import UniformityFilter
from scanner.anomaly_alerts import build_anomaly_messages
from scanner.market_processing import aggregate_daily_bars_from_hourly
from scanner.regime_filter import evaluate_regime_gate
from utils.insights import compute_data_reliability


def compute_uniformities_from_ohlcv(
    coins_with_cg_ids: list[dict[str, Any]],
    *,
    cache: Any,
    gecko: Any,
    history_fallback: Any,
    settings: Any,
    app_logger: Any,
    gain_qualified_total: int,
    coins_without_cg_ids: list[str],
    no_ticker_count: int,
    coins_with_cg_count: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    """
    FILTER 2: fetch/cache hourly OHLCV, aggregate daily bars, compute uniformity scores.
    Returns (all_processed, all_processed_map, anomaly_messages).
    """
    app_logger.info("\n📐 FILTER 2: Calculating uniformity scores...")

    cached_coins: list[dict[str, Any]] = []
    uncached_coins: list[dict[str, Any]] = []

    for coin in coins_with_cg_ids:
        found, cached = cache.get_price_data(coin["cg_id"])
        if found and cached:
            coin["uniformity_score"] = cached["uniformity_score"]
            coin["total_gain"] = cached["gains_30d"]
            coin["ohlcv_source"] = "price_cache"
            coin["quality_candles"] = 0
            cached_coins.append(coin)
            app_logger.info(f"   ✓ {coin['symbol']}: Using cached (score: {cached['uniformity_score']:.1f})")
        else:
            uncached_coins.append(coin)

    app_logger.info(f"\n   Cached: {len(cached_coins)}, Need fetching: {len(uncached_coins)}")

    uniformity_days = settings.uniformity_period
    for i, coin in enumerate(uncached_coins, 1):
        app_logger.info(f"\n   [{i}/{len(uncached_coins)}] {coin['symbol']}")

        ohlcv_source = "none"
        found, cached_rows = cache.get_ohlcv_rows(
            "coingecko", coin["symbol"], "1h", max_age_hours=settings.cache_price_hours
        )
        hourly_rows = cached_rows if found and cached_rows else None
        if hourly_rows:
            ohlcv_source = "coingecko_cache"
        else:
            api_rows = gecko.get_hourly_ohlcv(coin["cg_id"], days=max(30, uniformity_days))
            if api_rows:
                cache.cache_ohlcv_rows("coingecko", coin["symbol"], "1h", api_rows, source="coingecko_api")
                hourly_rows = api_rows
                ohlcv_source = "coingecko_api"

        if not hourly_rows:
            found_polygon, cached_polygon_rows = cache.get_ohlcv_rows(
                "polygon", coin["symbol"], "1h", max_age_hours=settings.cache_price_hours
            )
            if found_polygon and cached_polygon_rows:
                hourly_rows = cached_polygon_rows
                ohlcv_source = "polygon_cache"
            else:
                polygon_rows = history_fallback.get_polygon_30d_hourly_ohlcv(coin["symbol"])
                if polygon_rows:
                    cache.cache_ohlcv_rows("polygon", coin["symbol"], "1h", polygon_rows, source="polygon_api")
                    hourly_rows = polygon_rows
                    ohlcv_source = "polygon_api"

        if not hourly_rows:
            found_cmc, cached_cmc_rows = cache.get_ohlcv_rows(
                "cmc", coin["symbol"], "1h", max_age_hours=settings.cache_price_hours
            )
            if found_cmc and cached_cmc_rows:
                hourly_rows = cached_cmc_rows
                ohlcv_source = "cmc_cache"
            else:
                cmc_hourly = history_fallback.get_cmc_hourly_ohlcv(coin["symbol"], days=max(30, uniformity_days))
                if cmc_hourly:
                    cache.cache_ohlcv_rows("cmc", coin["symbol"], "1h", cmc_hourly, source="cmc_api")
                    hourly_rows = cmc_hourly
                    ohlcv_source = "cmc_api"

        if not hourly_rows:
            app_logger.info("      ⏳ No OHLCV data available - will retry next scan")
            continue

        coin["quality_candles"] = len(hourly_rows)
        coin["ohlcv_source"] = ohlcv_source

        daily_bars = aggregate_daily_bars_from_hourly(hourly_rows)
        if len(daily_bars) < uniformity_days:
            app_logger.info("      ⚠️ Insufficient OHLCV history")
            continue

        score, gain = UniformityFilter.calculate_from_ohlcv(daily_bars, uniformity_days)
        coin["uniformity_score"] = score
        coin["total_gain"] = gain

        closes_for_cache = [float(bar["close"]) for bar in daily_bars[-uniformity_days:]]
        cache.cache_price_data(coin["cg_id"], closes_for_cache, score, gain)
        app_logger.info(f"      ✅ Score: {score:.1f}, Return: {gain:+.1f}% ({ohlcv_source})")

    all_processed = cached_coins + [c for c in uncached_coins if "uniformity_score" in c]
    all_processed_map = {c["symbol"]: c for c in all_processed}
    for coin in all_processed:
        compute_data_reliability(coin)

    anomaly_messages = build_anomaly_messages(
        total_gain_qualified=gain_qualified_total,
        missing_cg_count=len(coins_without_cg_ids),
        no_ticker_count=no_ticker_count,
        cg_mapped_count=coins_with_cg_count,
        processed_ohlcv_count=len(all_processed),
        max_missing_cg_ratio=settings.anomaly_max_missing_cg_ratio,
        max_no_ticker_ratio=settings.anomaly_max_no_ticker_ratio,
        min_ohlcv_success_ratio=settings.anomaly_min_ohlcv_success_ratio,
    )
    if anomaly_messages:
        app_logger.warning("⚠️ Anomaly detector triggered:")
        for message in anomaly_messages:
            app_logger.warning(f"   - {message}")

    return all_processed, all_processed_map, anomaly_messages


def apply_uniformity_pass_and_regime(
    all_processed: list[dict[str, Any]],
    all_cmc_coins: list[dict[str, Any]],
    *,
    settings: Any,
    app_logger: Any,
) -> tuple[list[dict[str, Any]], set[str], dict[str, Any] | None]:
    """
    FILTER 3 + optional regime gate.

    Returns (uniformity_passed, uniformity_passed_symbols, regime_gate_or_none).
    ``regime_gate`` is a JSON-safe dict when ``REGIME_FILTER_ENABLED``; otherwise None.
    """
    app_logger.info(f"\n📐 FILTER 3: Applying uniformity filter (min: {settings.uniformity_min_score})...")

    uniformity_passed: list[dict[str, Any]] = []

    for coin in all_processed:
        if (
            "uniformity_score" in coin
            and coin["uniformity_score"] >= settings.uniformity_min_score
            and coin["total_gain"] > 0
        ):
            uniformity_passed.append(coin)
            app_logger.info(f"   ✓ {coin['symbol']}: Score {coin['uniformity_score']:.1f}")
        else:
            app_logger.info(
                f"   ❌ {coin['symbol']}: Failed uniformity filter "
                f"(score={float(coin.get('uniformity_score', 0.0) or 0.0):.1f})"
            )

    uniformity_passed_symbols = {c["symbol"] for c in uniformity_passed}

    regime_meta: dict[str, Any] | None = None
    if settings.regime_filter_enabled:
        regime_ok, regime_reason, regime_ctx = evaluate_regime_gate(
            all_cmc_coins,
            btc_min_30d_gain=settings.regime_filter_btc_min_30d_gain,
            btc_max_abs_7d_gain=settings.regime_filter_btc_max_abs_7d_gain,
        )
        g7 = float(regime_ctx.get("btc_7d", 0.0) or 0.0)
        g30 = float(regime_ctx.get("btc_30d", 0.0) or 0.0)
        regime_meta = {
            "enabled": True,
            "passed": bool(regime_ok),
            "blocked": not regime_ok,
            "reason": str(regime_reason),
            "btc_7d_pct": round(g7, 4),
            "btc_30d_pct": round(g30, 4),
            "btc_min_30d_gain_pct": float(settings.regime_filter_btc_min_30d_gain),
            "btc_max_abs_7d_gain_pct": float(settings.regime_filter_btc_max_abs_7d_gain),
        }
        if regime_ok:
            if regime_ctx:
                app_logger.info(
                    "🌦️ Regime filter pass: btc_7d=%.2f%% btc_30d=%.2f%%",
                    g7,
                    g30,
                )
            else:
                app_logger.info("🌦️ Regime filter pass: %s", regime_reason)
        else:
            app_logger.warning("🌦️ Regime filter blocked qualification: %s", regime_reason)
            uniformity_passed = []
            uniformity_passed_symbols = set()

    return uniformity_passed, uniformity_passed_symbols, regime_meta
