"""Coin enrichment helpers for ranking and annotation (Milestone I2 extraction)."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from backtesting.data_loader import BacktestDataLoader
from backtesting.signals import generate_indicator_signals

# Dashboard sparklines: separate 7d vs 30d windows at 1h resolution (30 * 24 bars).
SPARKLINE_HOURLY_MAX_BARS = 30 * 24


def attach_rank_movement(final_results: list[dict], previous_rank_map: dict[str, int]) -> None:
    for rank, coin in enumerate(final_results, start=1):
        symbol = str(coin.get("symbol", "")).upper()
        previous_rank = previous_rank_map.get(symbol)
        coin["current_rank"] = rank
        coin["previous_rank"] = previous_rank
        if previous_rank is None:
            coin["rank_status"] = "new"
            coin["rank_delta"] = None
        else:
            delta = previous_rank - rank
            coin["rank_delta"] = delta
            if delta > 0:
                coin["rank_status"] = "up"
            elif delta < 0:
                coin["rank_status"] = "down"
            else:
                coin["rank_status"] = "flat"


def _format_signal_age_label(bars_ago: int, timeframe: str) -> str:
    normalized = str(timeframe or "1h").lower()
    hours_per_bar = {
        "1h": 1,
        "4h": 4,
        "1d": 24,
        "daily": 24,
    }.get(normalized, 1)

    if bars_ago <= 0:
        return f"current candle ({normalized})"

    approx_hours = bars_ago * hours_per_bar
    if approx_hours < 24:
        approx_label = f"~{approx_hours}h"
    else:
        approx_days = approx_hours / 24
        approx_label = f"~{approx_days:.1f}d" if approx_days % 1 else f"~{int(approx_days)}d"

    candle_label = "candle" if bars_ago == 1 else "candles"
    return f"{bars_ago} {candle_label} ago on {normalized} ({approx_label})"


def attach_signal_age(coin: dict, loader: BacktestDataLoader, logger: Any | None = None) -> None:
    strategies = coin.get("backtest_top_strategies") or []
    if not strategies:
        return

    best_strategy = strategies[0]
    indicator = str(best_strategy.get("indicator", "")).strip()
    timeframe = str(best_strategy.get("timeframe", "1h")).strip().lower()
    params = best_strategy.get("params") or {}

    if not indicator or indicator == "B&H":
        return

    loaded = loader.load(
        symbol=str(coin.get("symbol", "")).upper(),
        timeframe=timeframe,
        days=30,
        gecko_id=coin.get("gecko_id") or coin.get("cg_id"),
    )
    if loaded.frame is None or loaded.frame.empty:
        return

    try:
        buy_signals, sell_signals = generate_indicator_signals(indicator=indicator, frame=loaded.frame, params=params)
    except Exception as signal_error:
        if logger is not None:
            logger.warning(f"⚠️ Signal age skipped for {coin.get('symbol', '?')}: {signal_error}")
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

    coin["signal_age_bars"] = bars_ago
    coin["signal_age_timeframe"] = timeframe
    coin["signal_age_label"] = _format_signal_age_label(bars_ago, timeframe)
    coin["signal_age_indicator"] = indicator
    coin["signal_age_active"] = signal_is_active


def attach_volume_acceleration(coin: dict, loader: BacktestDataLoader) -> None:
    loaded = loader.load(
        symbol=str(coin.get("symbol", "")).upper(),
        timeframe="1h",
        days=10,
        gecko_id=coin.get("gecko_id") or coin.get("cg_id"),
    )
    if loaded.frame is None or loaded.frame.empty:
        return

    volume = loaded.frame["volume"].astype(float)
    if len(volume) < 48:
        return

    current_window = volume.iloc[-24:] if len(volume) >= 24 else volume
    previous_volume = volume.iloc[:-24]
    prior_window_count = min(7, len(previous_volume) // 24)
    if prior_window_count <= 0:
        return

    baseline_hours = previous_volume.iloc[-(prior_window_count * 24) :]
    baseline_daily_totals = [
        float(baseline_hours.iloc[start : start + 24].sum())
        for start in range(0, len(baseline_hours), 24)
        if len(baseline_hours.iloc[start : start + 24]) == 24
    ]
    if not baseline_daily_totals:
        return

    current_24h_volume = float(current_window.sum())
    baseline_avg = float(sum(baseline_daily_totals) / len(baseline_daily_totals))
    if baseline_avg <= 0:
        return

    acceleration_pct = ((current_24h_volume - baseline_avg) / baseline_avg) * 100.0
    coin["volume_acceleration_pct"] = acceleration_pct
    coin["volume_acceleration_window_days"] = len(baseline_daily_totals)
    coin["volume_recent_24h"] = current_24h_volume
    coin["volume_baseline_24h"] = baseline_avg


def _closes_for_symbol_keys(
    db_path: Path,
    symbol_keys: list[str],
    *,
    max_bars: int,
) -> list[float]:
    """Last ``max_bars`` 1h closes for the given cache symbol keys (oldest→newest)."""
    keys = [str(k).strip() for k in symbol_keys if str(k or "").strip()]
    if not keys or not db_path.is_file():
        return []
    placeholders = ",".join("?" for _ in keys)
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.execute(
                f"""
                SELECT ts, close
                FROM ohlcv_cache
                WHERE symbol IN ({placeholders}) AND timeframe = '1h'
                ORDER BY ts ASC
                """,
                tuple(keys),
            )
            rows = cur.fetchall()
    except Exception:
        return []
    by_ts: dict[int, list[float]] = defaultdict(list)
    for ts, close in rows:
        if close is None:
            continue
        try:
            by_ts[int(ts)].append(float(close))
        except (TypeError, ValueError):
            continue
    ordered_ts = sorted(by_ts.keys())
    closes = [sum(by_ts[t]) / len(by_ts[t]) for t in ordered_ts]
    if len(closes) > max_bars:
        closes = closes[-max_bars:]
    return closes


def _hourly_closes_from_scanner_db(
    db_path: Path,
    symbol: str,
    *,
    asset_id: str | None = None,
    max_bars: int = SPARKLINE_HOURLY_MAX_BARS,
) -> list[float]:
    """Last ``max_bars`` 1h closes (oldest→newest).

    Prefer CoinGecko ``asset_id`` cache rows (id-keyed) so ticker remaps do not
    mix foreign candles; fall back to ticker keys (Polygon / legacy).
    """
    aid = str(asset_id or "").strip().lower()
    sym = str(symbol or "").strip().upper()
    if aid:
        id_closes = _closes_for_symbol_keys(db_path, [aid], max_bars=max_bars)
        if len(id_closes) >= 2:
            return id_closes
        if aid.isdigit():
            cmc_closes = _closes_for_symbol_keys(db_path, [f"id:{aid}"], max_bars=max_bars)
            if len(cmc_closes) >= 2:
                return cmc_closes
    if not sym:
        return []
    return _closes_for_symbol_keys(db_path, [sym], max_bars=max_bars)


def attach_hourly_sparkline_closes_for_snapshot(
    coins: list[dict[str, Any]],
    scanner_db_path: Path,
    *,
    max_bars: int = SPARKLINE_HOURLY_MAX_BARS,
    logger: Any | None = None,
) -> None:
    """Attach ``closes_1h`` (1h OHLCV closes) for dashboard 7d / 30d sparklines."""
    path = Path(scanner_db_path)
    if not coins or not path.is_file():
        return
    for coin in coins:
        sym = str(coin.get("symbol", "") or "").strip()
        if not sym:
            continue
        asset_id = str(coin.get("cg_id") or coin.get("gecko_id") or "").strip() or None
        try:
            series = _hourly_closes_from_scanner_db(
                path, sym, asset_id=asset_id, max_bars=max_bars
            )
        except Exception as exc:
            if logger is not None:
                logger.warning("⚠️ closes_1h skipped for %s: %s", sym, exc)
            continue
        if len(series) >= 2:
            coin["closes_1h"] = series
