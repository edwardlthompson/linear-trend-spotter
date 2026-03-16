"""Image rendering utilities for Telegram notifications."""

from __future__ import annotations

import io
import sqlite3
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd

from config.settings import settings
from notifications.formatter import MessageFormatter
from backtesting.engine import run_backtest
from backtesting.models import BacktestConfig
from backtesting.signals import generate_indicator_signals


def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _parse_iso(value: str | None) -> Optional[datetime]:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _format_pct(value: Optional[float]) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):+.2f}%"
    return "n/a"


def _format_money(value: Optional[float]) -> str:
    if isinstance(value, (int, float)):
        return f"${float(value):,.6g}" if abs(float(value)) < 1 else f"${float(value):,.2f}"
    return "n/a"


def _resolve_trailing_stop_pct(item: Dict) -> float:
    raw_value = item.get("trailing_stop_loss_pct", item.get("trailing_stop_pct"))
    try:
        value = float(raw_value)
    except Exception:
        return 1.0
    return 1.0 if value < 1.0 else value


def _time_on_list_label(entered_at: Optional[datetime], exited_at: Optional[datetime]) -> str:
    if not entered_at or not exited_at:
        return "n/a"
    delta = exited_at - entered_at
    if delta.total_seconds() < 0:
        return "n/a"
    total_hours = int(delta.total_seconds() // 3600)
    days = total_hours // 24
    hours = total_hours % 24
    if days > 0:
        return f"{days}d {hours}h"
    return f"{hours}h"


def build_exit_notification_image(coin: Dict, db_path: Path, lookback_hours: int = 336) -> Optional[bytes]:
    """Render an exit dashboard image.

    Layout spec:
    1) Top main feature: mini price chart (1h close) with entry/exit markers.
    2) Bottom left panel: lifecycle and risk metrics.
    3) Bottom right panel: momentum, liquidity, and timing context.
    """
    symbol = str(coin.get('symbol', '')).upper()
    if not symbol:
        return None

    entry_price = _safe_float(coin.get('entry_price'))
    exit_price = _safe_float(coin.get('exit_price'))
    gain_7d = _safe_float(coin.get('gain_7d'))
    gain_30d = _safe_float(coin.get('gain_30d'))
    volume_24h = _safe_float(coin.get('volume_24h'))
    uniformity_score = _safe_float(coin.get('uniformity_score'))
    health_score = _safe_float(coin.get('health_score'))
    lifecycle_pnl_pct = _safe_float(coin.get('lifecycle_pnl_pct'))
    max_runup_pct = _safe_float(coin.get('max_runup_pct'))
    max_drawdown_pct = _safe_float(coin.get('max_drawdown_pct'))
    held_days = _safe_int(coin.get('held_days'))
    current_rank = coin.get('current_rank')

    entered_at = _parse_iso(coin.get('entered_date'))
    exited_at = _parse_iso(coin.get('exited_at')) or datetime.now(timezone.utc)
    cooldown_until = _parse_iso(coin.get('cooldown_until'))

    chart_points: List[tuple[int, float]] = []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ts, close
                FROM ohlcv_cache
                WHERE symbol = ? AND timeframe = '1h'
                ORDER BY ts DESC
                LIMIT ?
                """,
                (symbol, max(72, int(lookback_hours))),
            )
            fetched = cursor.fetchall()
            chart_points = [(int(row[0]), float(row[1])) for row in reversed(fetched) if row and row[1] is not None]
    except Exception:
        chart_points = []

    fig = plt.figure(figsize=(12, 8), dpi=170)
    gs = fig.add_gridspec(2, 2, height_ratios=[2.4, 1.4], width_ratios=[1, 1], hspace=0.18, wspace=0.12)
    fig.patch.set_facecolor("#0f172a")

    ax_chart = fig.add_subplot(gs[0, :])
    ax_chart.set_facecolor("#111827")
    ax_chart.set_title(f"{symbol} Exit Snapshot", fontsize=15, fontweight="bold", color="#e2e8f0", pad=10)
    ax_chart.grid(color="#374151", alpha=0.35, linewidth=0.6)
    ax_chart.tick_params(colors="#cbd5e1")

    if chart_points:
        x_values = list(range(len(chart_points)))
        close_values = [item[1] for item in chart_points]
        ts_values = [item[0] for item in chart_points]
        ax_chart.plot(x_values, close_values, color="#38bdf8", linewidth=1.8)

        entry_idx = 0
        if entered_at:
            entry_ts = int(entered_at.timestamp())
            entry_idx = min(range(len(ts_values)), key=lambda idx: abs(ts_values[idx] - entry_ts))
        elif entry_price is not None:
            entry_idx = min(range(len(close_values)), key=lambda idx: abs(close_values[idx] - entry_price))

        exit_idx = len(close_values) - 1

        plotted_entry_price = entry_price if entry_price is not None else close_values[entry_idx]
        plotted_exit_price = exit_price if exit_price is not None else close_values[exit_idx]

        ax_chart.scatter([entry_idx], [plotted_entry_price], color="#22c55e", s=70, zorder=4)
        ax_chart.annotate(
            "ENTRY",
            (entry_idx, plotted_entry_price),
            textcoords="offset points",
            xytext=(8, 10),
            color="#22c55e",
            fontsize=9,
            weight="bold",
        )

        ax_chart.scatter([exit_idx], [plotted_exit_price], color="#ef4444", s=80, zorder=4)
        ax_chart.annotate(
            "EXIT",
            (exit_idx, plotted_exit_price),
            textcoords="offset points",
            xytext=(8, -16),
            color="#f87171",
            fontsize=9,
            weight="bold",
        )

        ax_chart.set_xlabel("Recent 1h candles", color="#94a3b8")
        ax_chart.set_ylabel("Price", color="#94a3b8")
    else:
        ax_chart.text(0.5, 0.5, "No cached 1h OHLCV data for chart", ha="center", va="center", color="#cbd5e1")
        ax_chart.set_xticks([])
        ax_chart.set_yticks([])

    ax_left = fig.add_subplot(gs[1, 0])
    ax_left.axis("off")
    ax_left.set_facecolor("#0b1220")
    left_lines = [
        "Lifecycle & Risk",
        f"Exit reason: {str(coin.get('exit_reason') or 'n/a')}",
        f"Since-entry return: {_format_pct(lifecycle_pnl_pct)}",
        f"Max run-up: {_format_pct(max_runup_pct)}",
        f"Max drawdown: {_format_pct(max_drawdown_pct)}",
        f"Held: {held_days}d" if held_days is not None else "Held: n/a",
        f"Health score: {health_score:.1f}/100" if health_score is not None else "Health score: n/a",
        f"Uniformity: {uniformity_score:.1f}/100" if uniformity_score is not None else "Uniformity: n/a",
    ]
    ax_left.text(0.02, 0.96, "\n".join(left_lines), va="top", ha="left", fontsize=10, color="#e2e8f0")

    ax_right = fig.add_subplot(gs[1, 1])
    ax_right.axis("off")
    ax_right.set_facecolor("#0b1220")
    price_delta_pct = None
    if entry_price and exit_price and entry_price > 0:
        price_delta_pct = ((exit_price - entry_price) / entry_price) * 100.0

    right_lines = [
        "Market Context",
        f"Entry price: {_format_money(entry_price)}",
        f"Exit price: {_format_money(exit_price)}",
        f"Price delta: {_format_pct(price_delta_pct)}",
        f"7d gain: {_format_pct(gain_7d)}",
        f"30d gain: {_format_pct(gain_30d)}",
        f"24h volume: {_format_money(volume_24h)}",
        f"Rank at exit: #{current_rank}" if isinstance(current_rank, int) else "Rank at exit: n/a",
        f"On-list duration: {_time_on_list_label(entered_at, exited_at)}",
        f"Exited at: {exited_at.strftime('%Y-%m-%d %H:%M UTC')}",
        (
            f"Cooldown until: {cooldown_until.strftime('%Y-%m-%d %H:%M UTC')}"
            if cooldown_until else "Cooldown until: n/a"
        ),
    ]
    ax_right.text(0.02, 0.96, "\n".join(right_lines), va="top", ha="left", fontsize=10, color="#e2e8f0")

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()


def build_fallback_chart_image(symbol: str, db_path: Path) -> Optional[bytes]:
    """Build a line chart from cached 1h OHLCV closes when Chart-IMG is unavailable."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ts, close
                FROM ohlcv_cache
                WHERE symbol = ? AND timeframe = '1h'
                ORDER BY ts ASC
                """,
                (symbol.upper(),),
            )
            rows = cursor.fetchall()

        if not rows:
            return None

        closes = [float(item[1]) for item in rows]
        x_axis = list(range(len(closes)))

        fig, axis = plt.subplots(figsize=(12, 5), dpi=150)
        fig.patch.set_facecolor("#0b1220")
        axis.set_facecolor("#111827")
        axis.plot(x_axis, closes, color="#00d4ff", linewidth=1.6)
        axis.grid(color="#374151", alpha=0.35, linewidth=0.6)
        axis.tick_params(colors="#d1d5db")
        axis.set_title(f"{symbol.upper()} 1h Close (cached fallback)", color="#e5e7eb", fontsize=12, weight="bold")
        axis.set_xlabel("Candles", color="#9ca3af")
        axis.set_ylabel("Price", color="#9ca3af")

        output = io.BytesIO()
        fig.savefig(output, format="png", bbox_inches="tight")
        plt.close(fig)
        output.seek(0)
        return output.read()
    except Exception:
        return None


def build_strategy_table_image(coin: Dict) -> Optional[bytes]:
    """Build bordered strategy table image (top strategies + B&H)."""
    all_strategies = list(coin.get("backtest_top_strategies", []))
    buy_hold = coin.get("backtest_buy_hold")

    if not all_strategies and not buy_hold:
        return None

    bh_net = float(buy_hold.get("net_pct", float("-inf"))) if buy_hold else float("-inf")
    better_strategies = [s for s in all_strategies if float(s.get("net_pct", 0.0)) > bh_net]

    table_body: List[List[str]] = []

    def append_row(item: Dict):
        indicator = str(item.get("indicator", "Unknown"))
        timeframe = str(item.get("timeframe", "?"))
        key_settings = MessageFormatter._format_key_settings(item.get("params", {}) or {})
        key_settings = "\n".join(textwrap.wrap(key_settings, width=30)) if key_settings else "none"

        if indicator == "B&H":
            stop_loss = "-"
            trades = "-"
            tsl_hits = "-"
            win_pct = "-"
        else:
            stop_loss = f"{_resolve_trailing_stop_pct(item):.2f}%"
            trades = str(int(item.get("trades", 0)))
            tsl_hits = str(int(item.get("tsl_hits", 0)))
            win_pct = f"{float(item.get('win_pct', 0.0)):.2f}%"

        table_body.append(
            [
                indicator,
                timeframe,
                key_settings,
                stop_loss,
                f"${float(item.get('final_equity', 0.0)):,.2f}",
                f"{float(item.get('net_pct', 0.0)):+.2f}%",
                trades,
                tsl_hits,
                win_pct,
            ]
        )

    strategy_rows = sorted(all_strategies, key=lambda s: float(s.get("net_pct", 0.0)), reverse=True)

    if better_strategies:
        sorted_better = sorted(better_strategies, key=lambda s: float(s.get("net_pct", 0.0)), reverse=True)
        for row in sorted_better:
            append_row(row)
        if buy_hold:
            table_body.append([""] * 9)
            append_row(buy_hold)
    else:
        if buy_hold:
            append_row(buy_hold)
            table_body.append([""] * 9)
        for row in strategy_rows[:5]:
            append_row(row)

    headers = ["Indicator", "TF", "Key Settings", "TSL %", "Final $", "Net %", "Trades", "TSL Hits", "Win %"]
    fig, axis = plt.subplots(figsize=(12, 4.9), dpi=160)
    fig.patch.set_facecolor("#0f172a")
    axis.set_facecolor("#0f172a")
    axis.axis("off")
    symbol = str(coin.get("symbol", "?")).upper()
    axis.set_title(
        f"{symbol}/USD • Backtest Ranked Strategies",
        fontsize=12,
        fontweight="bold",
        pad=10,
        color="#e2e8f0",
    )

    table = axis.table(
        cellText=table_body,
        colLabels=headers,
        colWidths=[0.11, 0.06, 0.28, 0.09, 0.1, 0.08, 0.08, 0.09, 0.08],
        loc="center",
        cellLoc="left",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.45)

    for (row_index, col_index), cell in table.get_celld().items():
        cell.set_edgecolor("#334155")
        cell.set_linewidth(0.8)
        if row_index == 0:
            cell.set_facecolor("#1e3a8a")
            cell.set_text_props(weight="bold", color="#f8fafc")
            continue

        row_values = table_body[row_index - 1]
        is_blank_separator = all(value == "" for value in row_values)
        if is_blank_separator:
            cell.set_facecolor("#0f172a")
            cell.set_edgecolor("#0f172a")
            continue

        is_buy_hold = row_values[0] == "B&H"
        cell.set_facecolor("#111827" if is_buy_hold else "#0b1220")
        cell.get_text().set_color("#e2e8f0")
        if is_buy_hold:
            cell.set_text_props(weight="bold")

        if col_index == 5:
            net_text = str(row_values[5])
            if net_text.startswith('+'):
                cell.get_text().set_color("#22c55e")
            elif net_text.startswith('-'):
                cell.get_text().set_color("#f87171")

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()


def build_combined_notification_image(coin: Dict, db_path: Path) -> Optional[bytes]:
    """Build one image containing the price chart on top (with strategy Signals) and ranked table below."""
    symbol = str(coin.get('symbol', '')).upper()
    if not symbol:
        return None

    all_strategies_raw = list(coin.get("backtest_top_strategies", []))
    all_strategies = []
    for s in all_strategies_raw:
        if float(s.get("win_pct", 0.0)) < 70.0: continue
        trades_cnt = int(s.get("trades", 0))
        tsl_hits_cnt = int(s.get("tsl_hits", 0))
        if trades_cnt > 0 and (tsl_hits_cnt / trades_cnt) > 0.50: continue
        all_strategies.append(s)

    buy_hold = coin.get("backtest_buy_hold")
    
    # 1. Fetch OHLCV data for local rendering
    chart_points: List[tuple] = []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ts, open, high, low, close, volume
                FROM ohlcv_cache
                WHERE symbol = ? AND timeframe = '1h'
                ORDER BY ts ASC
                """,
                (symbol,),
            )
            fetched = cursor.fetchall()
            # Keep all for backtest calculation warmup
            chart_points = fetched
    except Exception:
        chart_points = []

    # 2. Build table body (Same as original)
    bh_net = float(buy_hold.get("net_pct", float("-inf"))) if buy_hold else float("-inf")
    better_strategies = [s for s in all_strategies if float(s.get("net_pct", 0.0)) > bh_net]

    table_body: List[List[str]] = []

    def append_row(item: Dict):
        indicator = str(item.get("indicator", "Unknown"))
        timeframe = str(item.get("timeframe", "?"))
        key_settings = MessageFormatter._format_key_settings(item.get("params", {}) or {})
        key_settings = "\n".join(textwrap.wrap(key_settings, width=30)) if key_settings else "none"

        if indicator == "B&H":
            stop_loss = "-"
            trades = "-"
            tsl_hits = "-"
            tsl_hit_pct = "-"
            win_pct = "-"
        else:
            stop_loss = f"{_resolve_trailing_stop_pct(item):.2f}%"
            trades_cnt = int(item.get("trades", 0))
            tsl_hits_cnt = int(item.get("tsl_hits", 0))
            trades = str(trades_cnt)
            tsl_hits = str(tsl_hits_cnt)
            tsl_hit_pct = f"{(tsl_hits_cnt / trades_cnt * 100.0):.1f}%" if trades_cnt > 0 else "0.0%"
            win_pct = f"{float(item.get('win_pct', 0.0)):.2f}%"

        table_body.append(
            [
                indicator,
                timeframe,
                key_settings,
                stop_loss,
                tsl_hits,
                tsl_hit_pct,
                f"${float(item.get('final_equity', 0.0)):,.2f}",
                f"{float(item.get('net_pct', 0.0)):+.2f}%",
                trades,
                win_pct,
            ]
        )

    strategy_rows = sorted(all_strategies, key=lambda s: float(s.get("net_pct", 0.0)), reverse=True)

    if better_strategies:
        sorted_better = sorted(better_strategies, key=lambda s: float(s.get("net_pct", 0.0)), reverse=True)
        for row in sorted_better:
            append_row(row)
        if buy_hold:
            table_body.append([""] * 10)
            append_row(buy_hold)
    else:
        if buy_hold:
            append_row(buy_hold)
            table_body.append([""] * 10)
        for row in strategy_rows[:5]:
            append_row(row)

    # Define top_strategies for downstream chart signal overlays (Line 515)
    top_strategies = strategy_rows

    # 3. Create Figure
    fig = plt.figure(figsize=(12, 10), dpi=160)
    fig.patch.set_facecolor("#0f172a")
    gs = fig.add_gridspec(2, 1, height_ratios=[2.8, 1.8], hspace=0.15)

    # 3a. Draw Chart
    ax_chart = fig.add_subplot(gs[0])
    ax_chart.set_facecolor("#111827")
    ax_chart.set_title(f"{symbol}/USD • Local Chart with Backtest Overlay", fontsize=13, fontweight="bold", color="#e2e8f0", pad=12)
    ax_chart.grid(color="#374151", alpha=0.35, linewidth=0.6)
    ax_chart.tick_params(colors="#cbd5e1")

    if chart_points:
        close_values = [float(item[4]) for item in chart_points]
        open_values = [float(item[1]) for item in chart_points]
        high_values = [float(item[2]) for item in chart_points]
        low_values = [float(item[3]) for item in chart_points]

        # Calculate ATR array for continuous envelope shading on 1h intervals
        true_ranges = []
        for index in range(len(close_values)):
            if index == 0:
                tr = high_values[index] - low_values[index]
            else:
                tr = max(
                    high_values[index] - low_values[index],
                    abs(high_values[index] - close_values[index - 1]),
                    abs(low_values[index] - close_values[index - 1]),
                )
            true_ranges.append(tr)
        atr_values = pd.Series(true_ranges).rolling(window=24, min_periods=1).mean().fillna(0).tolist()

        # 3a. Pre-calculate Backtest Results to get Dynamic Display Window
        start_idx = max(0, len(chart_points) - 144) 
        buy_signals = []
        sell_signals = []
        run_result = None
        
        if top_strategies:
            try:
                top_strat = top_strategies[0]
                indicator = str(top_strat.get('indicator', ''))
                params = top_strat.get('params', {}) or {}
                
                df = pd.DataFrame(chart_points, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['volume'].astype(float)
                df.set_index('ts', inplace=True)
                
                # Resample frame if strategy timeframe differs from default 1h chart points
                timeframe = str(top_strat.get('tf') or top_strat.get('timeframe') or '1h')
                if timeframe not in ('1h', '60m'):
                    rule = "4h" if timeframe == "4h" else "1d" if timeframe in ("1d", "daily") else timeframe
                    df.index = pd.to_datetime(df.index, unit='s', utc=True)
                    df = df.resample(rule).agg({
                        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
                    }).dropna(subset=["open", "high", "low", "close"])

                buy_signals, sell_signals = generate_indicator_signals(indicator, df, params)
                
                run_result = run_backtest(
                    frame=df,
                    buy_signals=buy_signals,
                    sell_signals=sell_signals,
                    config=BacktestConfig(
                        starting_capital=float(settings.backtest_starting_capital),
                        fee_bps_round_trip=float(settings.backtest_fee_bps_round_trip),
                        trailing_stop_loss_pct=float(top_strat.get("trailing_stop_loss_pct") or top_strat.get("trailing_stop_pct") or 1.0),
                        take_profit_pct=float(top_strat.get("take_profit_pct") or 0.0),
                        trailing_take_profit_pct=float(top_strat.get("trailing_take_profit_pct") or 0.0),
                    ),
                )
                
                index_lookup_1h = {str(item[0]): idx for idx, item in enumerate(chart_points)}
                
                def _lookup_pos(ts_raw) -> int | None:
                    try:
                        # 1. Digit string (Epoch) fallback first
                        ts_str = str(ts_raw).strip()
                        if ts_str.replace('.', '', 1).isdigit():
                            ts_epoch = str(int(float(ts_str)))
                            if ts_epoch in index_lookup_1h:
                                return index_lookup_1h[ts_epoch]
                        
                        # 2. DatetimeIndex Timestamp node fallback
                        ts_dt = pd.to_datetime(ts_raw)
                        ts_epoch = str(int(ts_dt.timestamp()))
                        return index_lookup_1h.get(ts_epoch)
                    except Exception:
                        return None

                trade_indices = []
                for trade in run_result.trades:
                    e_idx = _lookup_pos(str(trade.entry_time))
                    ex_idx = _lookup_pos(str(trade.exit_time))
                    if e_idx is not None: trade_indices.append(e_idx)
                    if ex_idx is not None: trade_indices.append(ex_idx)
                
                if trade_indices:
                    # Expand viewport to Earliest trade minus small buffer
                    start_idx = max(0, min(trade_indices) - 5)
            except Exception:
                pass

        display_close = close_values[start_idx:]
        display_open = open_values[start_idx:]
        display_high = high_values[start_idx:]
        display_low = low_values[start_idx:]

        # Draw solid line for price data to declutter dense grids
        x_values = list(range(len(display_close)))
        ax_chart.plot(x_values, display_close, color="#38bdf8", linewidth=1.2, zorder=3)

        # Draw shaded ATR Envelope bounds
        try:
            display_atr = atr_values[start_idx:]
            if len(display_atr) == len(display_close):
                atr_upper = [display_close[i] + display_atr[i] for i in range(len(display_close))]
                atr_lower = [display_close[i] - display_atr[i] for i in range(len(display_close))]
                ax_chart.fill_between(x_values, atr_lower, atr_upper, color="#38bdf8", alpha=0.07, label="ATR Band", zorder=1)
        except Exception:
            pass

        if display_close:
            last_close = display_close[-1]
            ax_chart.axhline(last_close, color="#cbd5e1", linestyle="--", linewidth=0.8, alpha=0.55, zorder=2)
            ax_chart.text(
                len(display_close), 
                last_close, 
                f" {last_close:,.2f}", 
                color="#cbd5e1", fontsize=7.5, va="center", ha="left",
                bbox=dict(facecolor="#1e293b", alpha=0.85, boxstyle="round,pad=0.15", linewidth=0),
                zorder=4
            )
            ax_chart.set_xlim(-1, len(display_close) + 8)
            ax_chart.set_ylim(min(display_low) * 0.988, max(display_high) * 1.012)

        ax_chart.set_ylabel("Price", color="#94a3b8")

        # Map signal scatter overlays using dynamic start_idx window alignment
        if run_result:
            try:
                signal_buy_idx = [idx - start_idx for idx, flag in enumerate(buy_signals) if bool(flag) and idx >= start_idx]
                signal_sell_idx = [idx - start_idx for idx, flag in enumerate(sell_signals) if bool(flag) and idx >= start_idx]

                # Removed signal dots to declutter chart

                buy_idx = []
                sell_idx = []
                for trade in run_result.trades:
                    entry_idx = _lookup_pos(str(trade.entry_time))
                    exit_idx = _lookup_pos(str(trade.exit_time))
                    
                    rel_entry = entry_idx - start_idx if entry_idx is not None else None
                    rel_exit = exit_idx - start_idx if exit_idx is not None else None
                    
                    if rel_entry is not None and rel_entry >= 0 and rel_entry < len(display_close):
                        buy_idx.append(rel_entry)
                        
                    if rel_exit is not None and rel_exit >= 0 and rel_exit < len(display_close):
                        sell_idx.append(rel_exit)
                        pnl = float(trade.pnl_pct)
                        color = "#22c55e" if pnl >= 0 else "#ef4444"
                        y_val = display_close[rel_exit]
                        
                        ax_chart.annotate(
                            f"{pnl:+.1f}%",
                            xy=(rel_exit, y_val), xytext=(0, 7 if pnl >= 0 else -7),
                            textcoords="offset points", color=color, fontsize=6.5, fontweight="bold",
                            ha="center", va="bottom" if pnl >= 0 else "top",
                            bbox=dict(facecolor="#0f172a", alpha=0.75, boxstyle="round,pad=0.12", linewidth=0),
                            zorder=6,
                        )

                        # Add shaded Colored Rectangle bounding box for trade duration and price bounds
                        if rel_entry is not None and rel_entry >= 0:
                            rect_color = "#10b981" if pnl >= 0 else "#ef4444"
                            entry_p = float(trade.entry_price)
                            exit_p = float(trade.exit_price)
                            rect = patches.Rectangle(
                                (rel_entry, min(entry_p, exit_p)),
                                rel_exit - rel_entry,
                                abs(exit_p - entry_p),
                                linewidth=0, facecolor=rect_color, alpha=0.14, zorder=2
                            )
                            ax_chart.add_patch(rect)

                if buy_idx:
                    ax_chart.scatter(
                        buy_idx, [display_close[i] for i in buy_idx],
                        color="#22c55e", s=55, marker="^", edgecolors="#14532d", linewidths=0.4, label="Entry", zorder=5,
                    )
                if sell_idx:
                    ax_chart.scatter(
                        sell_idx, [display_close[i] for i in sell_idx],
                        color="#ef4444", s=55,
                        
                        marker="v",
                        edgecolors="#7f1d1d",
                        linewidths=0.4,
                        label="Exit",
                        zorder=5,
                    )

                legend_handles, legend_labels = ax_chart.get_legend_handles_labels()
                if legend_handles:
                    ax_chart.legend(
                        loc="upper left",
                        facecolor="#1e293b",
                        edgecolor="#475569",
                        labelcolor="#cbd5e1",
                        fontsize=9,
                    )
            except Exception as e:
                pass # Silently proceed if signal derivation crashes on faulty shapes
    else:
        ax_chart.text(0.5, 0.5, "No cached 1h OHLCV data for chart", ha="center", va="center", color="#cbd5e1")

    # 3b. Draw Table (Same as original)
    ax_table = fig.add_subplot(gs[1])
    ax_table.set_facecolor("#0f172a")
    ax_table.axis("off")
    ax_table.set_title(
        f"{symbol}/USD • Backtest Ranked Strategies",
        fontsize=12,
        fontweight="bold",
        pad=8,
        color="#e2e8f0",
    )

    if table_body:
        headers = ["Indicator", "TF", "Key Settings", "TSL %", "TSL Hits", "TSL Hit %", "Final $", "Net %", "Trades", "Win %"]
        table = ax_table.table(
            cellText=table_body,
            colLabels=headers,
            colWidths=[0.11, 0.05, 0.22, 0.08, 0.08, 0.09, 0.1, 0.09, 0.08, 0.1],
            loc="center",
            cellLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.5)

        for (row_index, col_index), cell in table.get_celld().items():
            cell.set_edgecolor("#334155")
            cell.set_linewidth(0.8)
            if row_index == 0:
                cell.set_facecolor("#1e3a8a")
                cell.set_text_props(weight="bold", color="#f8fafc")
                continue

            row_values = table_body[row_index - 1]
            is_blank_separator = all(value == "" for value in row_values)
            if is_blank_separator:
                cell.set_facecolor("#0f172a")
                cell.set_edgecolor("#0f172a")
                continue

            is_buy_hold = row_values[0] == "B&H"
            cell.set_facecolor("#111827" if is_buy_hold else "#0b1220")
            cell.get_text().set_color("#e2e8f0")
            if is_buy_hold:
                cell.set_text_props(weight="bold")
            if col_index == 7:
                net_text = str(row_values[7])
                if net_text.startswith('+'):
                    cell.get_text().set_color("#22c55e")
                elif net_text.startswith('-'):
                    cell.get_text().set_color("#f87171")
    else:
        ax_table.text(
            0.5,
            0.5,
            "No backtest strategy rows available",
            ha="center",
            va="center",
            fontsize=10,
            color="#cbd5e1",
        )

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()


def build_hourly_summary_image(
    active_rows: List[Dict],
    watchlist_rows: List[Dict],
    regime: Optional[Dict] = None,
    drift: Optional[Dict] = None,
) -> Optional[bytes]:
    """Render a compact event dashboard image for Telegram summary sends."""
    try:
        top_active = list(active_rows[:12])
        top_watchlist = list(watchlist_rows[:6])

        fig = plt.figure(figsize=(12, 9), dpi=170)
        gs = fig.add_gridspec(3, 1, height_ratios=[0.8, 2.3, 1.7], hspace=0.20)
        fig.patch.set_facecolor("#0f172a")

        ax_header = fig.add_subplot(gs[0])
        ax_header.axis("off")
        ax_header.set_facecolor("#0f172a")
        regime_name = str((regime or {}).get("regime", "unknown"))
        drift_status = str((drift or {}).get("status", "stable"))
        avg_30d = float((regime or {}).get("avg_gain_30d", 0.0) or 0.0)
        ax_header.text(0.01, 0.72, "Scanner Event Dashboard", fontsize=16, fontweight="bold", color="#e2e8f0")
        ax_header.text(
            0.01,
            0.34,
            f"Regime: {regime_name} | Avg 30d gain: {avg_30d:+.1f}% | Drift: {drift_status} | Active: {len(active_rows)} | Watchlist: {len(watchlist_rows)}",
            fontsize=10,
            color="#cbd5e1",
        )
        if (drift or {}).get("notes"):
            ax_header.text(
                0.01,
                0.08,
                "Drift notes: " + "; ".join((drift or {}).get("notes", [])[:3]),
                fontsize=9,
                color="#94a3b8",
            )

        ax_active = fig.add_subplot(gs[1])
        ax_active.axis("off")
        ax_active.set_facecolor("#111827")
        ax_active.set_title("Active Rankings", fontsize=12, fontweight="bold", pad=8, color="#dbeafe")
        if top_active:
            active_table = []
            for row in top_active:
                active_table.append([
                    f"A#{row.get('active_rank', '?')}",
                    MessageFormatter._format_rank_change(str(row.get('rank_status', 'new')), row.get('rank_delta')),
                    str(row.get('symbol', '')).upper(),
                    MessageFormatter._format_score(row.get('health_score')),
                    MessageFormatter._format_pct(row.get('gain_since_entry_pct')),
                    str(row.get('time_on_list') or 'n/a'),
                ])
            table = ax_active.table(
                cellText=active_table,
                colLabels=["Rank", "Δ", "Symbol", "Health", "Since alert", "On list"],
                colWidths=[0.08, 0.08, 0.18, 0.14, 0.18, 0.14],
                loc="center",
                cellLoc="left",
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.4)
            for (row_index, col_index), cell in table.get_celld().items():
                cell.set_edgecolor("#334155")
                cell.set_linewidth(0.7)
                if row_index == 0:
                    cell.set_facecolor("#1e3a8a")
                    cell.set_text_props(color="#e2e8f0", weight="bold")
                    continue
                cell.set_facecolor("#0b1220")
                cell.get_text().set_color("#e2e8f0")
                if col_index in (4, 5):
                    text = cell.get_text().get_text()
                    cell.get_text().set_color("#22c55e" if text.startswith('+') else "#f87171" if text.startswith('-') else "#cbd5e1")
        else:
            ax_active.text(0.5, 0.5, "No active rows", ha="center", va="center", color="#cbd5e1")

        ax_watch = fig.add_subplot(gs[2])
        ax_watch.axis("off")
        ax_watch.set_facecolor("#111827")
        ax_watch.set_title("Watchlist", fontsize=12, fontweight="bold", pad=8, color="#bbf7d0")
        if top_watchlist:
            watch_table = []
            for row in top_watchlist:
                watch_table.append([
                    str(row.get('symbol', '')).upper(),
                    f"{float(row.get('watchlist_score', 0.0)):.0f}",
                    "; ".join((row.get('reasons') or [])[:2]),
                ])
            table = ax_watch.table(
                cellText=watch_table,
                colLabels=["Symbol", "Watch", "Reason"],
                colWidths=[0.14, 0.1, 0.64],
                loc="center",
                cellLoc="left",
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.35)
            for (row_index, col_index), cell in table.get_celld().items():
                cell.set_edgecolor("#334155")
                cell.set_linewidth(0.7)
                if row_index == 0:
                    cell.set_facecolor("#166534")
                    cell.set_text_props(color="#f0fdf4", weight="bold")
                    continue
                cell.set_facecolor("#0b1220")
                cell.get_text().set_color("#86efac" if col_index == 2 else "#e2e8f0")
        else:
            ax_watch.text(0.5, 0.5, "No watchlist candidates", ha="center", va="center", color="#cbd5e1")

        output = io.BytesIO()
        fig.savefig(output, format="png", bbox_inches="tight")
        plt.close(fig)
        output.seek(0)
        return output.read()
    except Exception:
        return None
