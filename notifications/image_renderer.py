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
