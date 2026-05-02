"""Runtime component initialization for scanner orchestration (Milestone I2)."""

from __future__ import annotations

import os
from typing import Any

from api.chart_img import ChartIMGClient
from api.coingecko import CoinGeckoClient
from api.coingecko_mapper import CoinGeckoMapper
from api.coinmarketcap import CoinMarketCapClient
from api.price_history_fallback import PriceHistoryFallbackClient
from api.tradingview_mapper import TradingViewMapper
from database.cache import PriceCache
from database.models import ActiveCoinsDatabase, HistoryDatabase
from exchange_data.exchange_db import ExchangeDatabase
from notifications.telegram import TelegramClient
from utils.logger import app_logger


def initialize_runtime_components(settings: Any) -> dict[str, Any]:
    history_db = HistoryDatabase(settings.db_paths["scanner"])
    active_db = ActiveCoinsDatabase(settings.db_paths["scanner"])
    cache = PriceCache(settings.db_paths["scanner"])

    exchange_db = ExchangeDatabase(settings.db_paths["exchanges"])
    tv_mapper = TradingViewMapper(settings.db_paths["tv_mappings"])

    cmc = CoinMarketCapClient(settings.cmc_api_key)
    app_logger.info("✅ CoinMarketCap client initialized")

    gecko = CoinGeckoClient(calls_per_minute=settings.coingecko_calls_per_minute)
    app_logger.info("✅ CoinGecko client initialized")

    history_fallback = PriceHistoryFallbackClient(
        polygon_api_key=os.getenv("POLYGON_API_KEY", ""),
        cmc_api_key=settings.cmc_api_key,
    )
    app_logger.info("✅ OHLCV fallback chain initialized (Polygon + CMC hourly/daily tertiary)")

    cg_mapper = CoinGeckoMapper(settings.db_paths["mappings"])
    stats = cg_mapper.get_stats()
    max_list_age_days = settings.cache_gecko_id_days
    if cg_mapper.should_refresh_list(max_list_age_days):
        app_logger.info(
            "📡 CoinGecko mappings %s — fetching /coins/list (refresh if empty or older than %sd)...",
            "empty" if int(stats.get("total_mappings") or 0) == 0 else "stale",
            max_list_age_days,
        )
        cg_mapper.update_mappings()
    else:
        app_logger.info(
            "✅ CoinGecko mapper ready with %s mappings (list fresh within %sd; skipping /coins/list)",
            stats["total_mappings"],
            max_list_age_days,
        )

    if settings.chart_img_api_key:
        ChartIMGClient(settings.chart_img_api_key, mapper=tv_mapper)
        app_logger.info("✅ Chart-IMG client initialized")
    else:
        app_logger.warning("⚠️ No Chart-IMG API key - charts disabled")

    telegram = None
    if settings.telegram_enabled and settings.telegram:
        telegram = TelegramClient(
            settings.telegram["bot_token"],
            settings.telegram["chat_id"],
        )
        app_logger.info("✅ Telegram client initialized")
    elif not settings.telegram_enabled:
        app_logger.debug(
            "Skipping Telegram client (delivery_mode=%s)",
            settings.delivery_mode,
        )
    else:
        app_logger.warning("⚠️ Telegram credentials missing - notifications disabled")

    cmc_slug_resolver = None
    if settings.cmc_slug_map_enabled and settings.cmc_api_key and str(settings.cmc_api_key).strip():
        from utils.cmc_slug_resolver import CmcSlugResolver

        cmc_slug_resolver = CmcSlugResolver(
            settings.DATA_DIR,
            map_cache_file=settings.cmc_slug_map_cache_file,
            learn_file=settings.cmc_slug_learn_file,
        )
        try:
            cmc_slug_resolver.load()
            if (
                not cmc_slug_resolver.by_symbol
                or cmc_slug_resolver.map_cache_is_stale(settings.cmc_slug_map_max_age_hours)
            ):
                app_logger.info("📥 Refreshing CMC cryptocurrency map cache (symbol→slug metadata)...")
                if not cmc_slug_resolver.refresh_map_from_api(cmc):
                    app_logger.warning(
                        "⚠️ CMC map refresh failed or empty; CMC deep links may fall back to CoinGecko until the map loads"
                    )
            else:
                app_logger.info(
                    "✅ CMC slug map cache loaded (%s symbols indexed, max age %sh)",
                    len(cmc_slug_resolver.by_symbol),
                    settings.cmc_slug_map_max_age_hours,
                )
        except Exception as slug_exc:
            app_logger.warning("⚠️ CMC slug resolver unavailable: %s", slug_exc)
            cmc_slug_resolver = None

    return {
        "history_db": history_db,
        "active_db": active_db,
        "cache": cache,
        "exchange_db": exchange_db,
        "tv_mapper": tv_mapper,
        "cmc": cmc,
        "gecko": gecko,
        "history_fallback": history_fallback,
        "cg_mapper": cg_mapper,
        "telegram": telegram,
        "cmc_slug_resolver": cmc_slug_resolver,
    }
