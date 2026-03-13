"""Image rendering utilities for Telegram notifications."""

from __future__ import annotations

import io
import sqlite3
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt

from notifications.formatter import MessageFormatter


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
    top_strategies = list(coin.get("backtest_top_strategies", [])[:5])
    buy_hold = coin.get("backtest_buy_hold")

    rows = list(top_strategies)
    if buy_hold:
        rows.append(buy_hold)

    if not rows:
        return None

    ranked_rows = sorted(rows, key=lambda item: float(item.get("net_pct", float("-inf"))), reverse=True)
    strategy_rows = [row for row in ranked_rows if str(row.get("indicator", "")) != "B&H"]
    buy_hold_rows = [row for row in ranked_rows if str(row.get("indicator", "")) == "B&H"]

    table_body: List[List[str]] = []

    def append_row(item: Dict):
        indicator = str(item.get("indicator", "Unknown"))
        timeframe = str(item.get("timeframe", "?"))
        key_settings = MessageFormatter._format_key_settings(item.get("params", {}) or {})
        key_settings = "\n".join(textwrap.wrap(key_settings, width=30)) if key_settings else "none"

        if indicator == "B&H":
            stop_loss = "-"
            trades = "-"
            win_pct = "-"
        else:
            stop_loss = f"{float(item.get('trailing_stop_pct') or 0.0):.2f}%"
            trades = str(int(item.get("trades", 0)))
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
                win_pct,
            ]
        )

    for row in strategy_rows:
        append_row(row)

    if buy_hold_rows:
        table_body.append(["", "", "", "", "", "", "", ""])
        for row in buy_hold_rows:
            append_row(row)

    headers = ["Indicator", "TF", "Key Settings", "Stop Loss %", "Final $", "Net %", "Trades", "Win %"]
    fig, axis = plt.subplots(figsize=(12, 4.9), dpi=160)
    axis.axis("off")
    symbol = str(coin.get("symbol", "?")).upper()
    axis.set_title(
        f"{symbol}/USD • Backtest Ranked Strategies",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )

    table = axis.table(
        cellText=table_body,
        colLabels=headers,
        colWidths=[0.12, 0.07, 0.32, 0.1, 0.1, 0.08, 0.08, 0.08],
        loc="center",
        cellLoc="left",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.45)

    for (row_index, _), cell in table.get_celld().items():
        cell.set_edgecolor("#4c4c4c")
        cell.set_linewidth(0.8)
        if row_index == 0:
            cell.set_facecolor("#e8eef7")
            cell.set_text_props(weight="bold", color="#111111")
            continue

        row_values = table_body[row_index - 1]
        is_blank_separator = all(value == "" for value in row_values)
        if is_blank_separator:
            cell.set_facecolor("#ffffff")
            cell.set_edgecolor("#ffffff")
            continue

        is_buy_hold = row_values[0] == "B&H"
        cell.set_facecolor("#f7f7f7" if is_buy_hold else "#ffffff")

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()


def build_combined_notification_image(coin: Dict, chart_bytes: bytes) -> Optional[bytes]:
    """Build one image containing the price chart on top and bordered strategy table below."""
    top_strategies = list(coin.get("backtest_top_strategies", [])[:5])
    buy_hold = coin.get("backtest_buy_hold")

    rows = list(top_strategies)
    if buy_hold:
        rows.append(buy_hold)

    image = plt.imread(io.BytesIO(chart_bytes), format="png")

    ranked_rows = sorted(rows, key=lambda item: float(item.get("net_pct", float("-inf"))), reverse=True) if rows else []
    strategy_rows = [row for row in ranked_rows if str(row.get("indicator", "")) != "B&H"]
    buy_hold_rows = [row for row in ranked_rows if str(row.get("indicator", "")) == "B&H"]

    table_body: List[List[str]] = []

    def append_row(item: Dict):
        indicator = str(item.get("indicator", "Unknown"))
        timeframe = str(item.get("timeframe", "?"))
        key_settings = MessageFormatter._format_key_settings(item.get("params", {}) or {})
        key_settings = "\n".join(textwrap.wrap(key_settings, width=30)) if key_settings else "none"

        if indicator == "B&H":
            stop_loss = "-"
            trades = "-"
            win_pct = "-"
        else:
            stop_loss = f"{float(item.get('trailing_stop_pct') or 0.0):.2f}%"
            trades = str(int(item.get("trades", 0)))
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
                win_pct,
            ]
        )

    for row in strategy_rows:
        append_row(row)

    if buy_hold_rows:
        table_body.append(["", "", "", "", "", "", "", ""])
        for row in buy_hold_rows:
            append_row(row)

    fig = plt.figure(figsize=(12, 9), dpi=160)
    gs = fig.add_gridspec(2, 1, height_ratios=[2.6, 2.0], hspace=0.08)

    ax_chart = fig.add_subplot(gs[0])
    ax_chart.imshow(image)
    ax_chart.axis("off")
    symbol = str(coin.get("symbol", "?")).upper()
    ax_chart.set_title(f"{symbol}/USD • Price Chart", fontsize=12, fontweight="bold", pad=8)

    ax_table = fig.add_subplot(gs[1])
    ax_table.axis("off")
    ax_table.set_title(f"{symbol}/USD • Backtest Ranked Strategies", fontsize=12, fontweight="bold", pad=8)

    if table_body:
        headers = ["Indicator", "TF", "Key Settings", "Stop Loss %", "Final $", "Net %", "Trades", "Win %"]
        table = ax_table.table(
            cellText=table_body,
            colLabels=headers,
            colWidths=[0.12, 0.07, 0.32, 0.1, 0.1, 0.08, 0.08, 0.08],
            loc="center",
            cellLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.5)

        for (row_index, _), cell in table.get_celld().items():
            cell.set_edgecolor("#4c4c4c")
            cell.set_linewidth(0.8)
            if row_index == 0:
                cell.set_facecolor("#e8eef7")
                cell.set_text_props(weight="bold", color="#111111")
                continue

            row_values = table_body[row_index - 1]
            is_blank_separator = all(value == "" for value in row_values)
            if is_blank_separator:
                cell.set_facecolor("#ffffff")
                cell.set_edgecolor("#ffffff")
                continue

            is_buy_hold = row_values[0] == "B&H"
            cell.set_facecolor("#f7f7f7" if is_buy_hold else "#ffffff")
    else:
        ax_table.text(
            0.5,
            0.5,
            "No backtest strategy rows available",
            ha="center",
            va="center",
            fontsize=10,
        )

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()


def build_hourly_summary_image(
    active_rows: List[Dict],
    warning_rows: List[Dict],
    watchlist_rows: List[Dict],
    regime: Optional[Dict] = None,
    drift: Optional[Dict] = None,
) -> Optional[bytes]:
    """Render a compact hourly dashboard image for Telegram summary sends."""
    try:
        top_active = list(active_rows[:12])
        top_warnings = list(warning_rows[:8])
        top_watchlist = list(watchlist_rows[:6])

        fig = plt.figure(figsize=(12, 11), dpi=170)
        gs = fig.add_gridspec(4, 1, height_ratios=[0.8, 2.2, 1.7, 1.6], hspace=0.20)
        fig.patch.set_facecolor("#0f172a")

        ax_header = fig.add_subplot(gs[0])
        ax_header.axis("off")
        ax_header.set_facecolor("#0f172a")
        regime_name = str((regime or {}).get("regime", "unknown"))
        drift_status = str((drift or {}).get("status", "stable"))
        avg_30d = float((regime or {}).get("avg_gain_30d", 0.0) or 0.0)
        ax_header.text(0.01, 0.72, "Hourly Scanner Dashboard", fontsize=16, fontweight="bold", color="#e2e8f0")
        ax_header.text(
            0.01,
            0.34,
            f"Regime: {regime_name} | Avg 30d gain: {avg_30d:+.1f}% | Drift: {drift_status} | Active: {len(active_rows)} | Warnings: {len(warning_rows)} | Watchlist: {len(watchlist_rows)}",
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
                    MessageFormatter._format_pct(row.get('gain_since_last_update_pct')),
                ])
            table = ax_active.table(
                cellText=active_table,
                colLabels=["Rank", "Δ", "Symbol", "Health", "Since alert", "1h"],
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

        ax_warn = fig.add_subplot(gs[2])
        ax_warn.axis("off")
        ax_warn.set_facecolor("#1f2937")
        ax_warn.set_title("Early Warnings", fontsize=12, fontweight="bold", pad=8, color="#fef3c7")
        if top_warnings:
            warning_table = []
            for row in top_warnings:
                reasons = "; ".join((row.get('reasons') or [])[:2])
                warning_table.append([
                    str(row.get('symbol', '')).upper(),
                    f"{float(row.get('health_score', 0.0) or 0.0):.0f}/100",
                    reasons,
                ])
            table = ax_warn.table(
                cellText=warning_table,
                colLabels=["Symbol", "Health", "Risk signals"],
                colWidths=[0.16, 0.14, 0.62],
                loc="center",
                cellLoc="left",
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.35)
            for (row_index, col_index), cell in table.get_celld().items():
                cell.set_edgecolor("#475569")
                cell.set_linewidth(0.7)
                if row_index == 0:
                    cell.set_facecolor("#92400e")
                    cell.set_text_props(color="#fffbeb", weight="bold")
                    continue
                cell.set_facecolor("#111827")
                cell.get_text().set_color("#fef3c7" if col_index == 2 else "#e2e8f0")
        else:
            ax_warn.text(0.5, 0.5, "No early warnings", ha="center", va="center", color="#cbd5e1")

        ax_watch = fig.add_subplot(gs[3])
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
