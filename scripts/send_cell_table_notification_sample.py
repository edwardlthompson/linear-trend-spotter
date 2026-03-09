"""Generate and send a sample Telegram notification image with chart + bordered table."""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.chart_img import ChartIMGClient
from backtesting.report import notification_rows_for_symbol
from config.settings import settings
from notifications.telegram import TelegramClient


def _load_active_coin(symbol: str) -> dict | None:
    db_path = settings.db_paths["scanner"]
    if not db_path.exists():
        return None

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT coin_symbol, coin_name, gain_7d, gain_30d, uniformity_score, slug
            FROM active_coins
            WHERE coin_symbol = ?
            """,
            (symbol,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "symbol": row[0],
        "name": row[1],
        "gains": {"7d": float(row[2] or 0.0), "30d": float(row[3] or 0.0)},
        "uniformity_score": float(row[4] or 0.0),
        "slug": row[5] or row[0].lower(),
    }


def _build_rows(symbol: str) -> tuple[list[list[str]], list[str]]:
    artifact_path = settings.base_dir / "backtest_results.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Backtest artifact not found: {artifact_path}")

    summary = json.loads(artifact_path.read_text(encoding="utf-8"))
    details = notification_rows_for_symbol(summary, symbol, top_n=5)

    rows = list(details.get("top_strategies", []))
    buy_hold = details.get("buy_hold")
    if buy_hold:
        rows.append(buy_hold)

    rows = sorted(rows, key=lambda item: float(item.get("net_pct", float("-inf"))), reverse=True)

    headers = ["Indicator", "TF", "Key Settings", "Stop Loss %", "Final $", "Net %", "Trades", "Win %"]
    body: list[list[str]] = []

    for row in rows:
        indicator = str(row.get("indicator", "Unknown"))
        timeframe = str(row.get("timeframe", "?"))
        params = row.get("params", {}) or {}
        key_settings = "; ".join(f"{k}={params[k]}" for k in sorted(params.keys())) if params else "none"

        if len(key_settings) > 52:
            key_settings = key_settings[:49] + "..."

        if indicator == "B&H":
            stop_loss = "-"
            trades = "-"
            win_pct = "-"
        else:
            stop_loss = f"{float(row.get('trailing_stop_pct') or 0.0):.2f}%"
            trades = str(int(row.get("trades", 0)))
            win_pct = f"{float(row.get('win_pct', 0.0)):.2f}%"

        body.append(
            [
                indicator,
                timeframe,
                key_settings,
                stop_loss,
                f"${float(row.get('final_equity', 0.0)):,.2f}",
                f"{float(row.get('net_pct', 0.0)):+.2f}%",
                trades,
                win_pct,
            ]
        )

    return body, headers


def _compose_image(chart_bytes: bytes, rows: list[list[str]], headers: list[str], output_path: Path, title: str) -> None:
    image = plt.imread(io.BytesIO(chart_bytes), format="png")

    fig = plt.figure(figsize=(12, 10), dpi=150)
    gs = fig.add_gridspec(2, 1, height_ratios=[2.8, 1.8], hspace=0.06)

    ax_chart = fig.add_subplot(gs[0])
    ax_chart.imshow(image)
    ax_chart.axis("off")
    ax_chart.set_title(title, fontsize=12, weight="bold", pad=8)

    ax_table = fig.add_subplot(gs[1])
    ax_table.axis("off")
    col_widths = [0.12, 0.07, 0.32, 0.1, 0.1, 0.08, 0.08, 0.08]

    table = ax_table.table(
        cellText=rows,
        colLabels=headers,
        colWidths=col_widths,
        loc="center",
        cellLoc="left",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.45)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#4c4c4c")
        cell.set_linewidth(0.8)
        if r == 0:
            cell.set_facecolor("#e8eef7")
            cell.set_text_props(weight="bold", color="#111111")
        else:
            indicator = rows[r - 1][0]
            if indicator == "B&H":
                cell.set_facecolor("#f7f7f7")
            else:
                cell.set_facecolor("#ffffff")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def _build_fallback_chart_from_cache(symbol: str) -> bytes:
    db_path = settings.db_paths["scanner"]
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ts, close
            FROM ohlcv_cache
            WHERE symbol = ? AND timeframe = '1h'
            ORDER BY ts ASC
            """,
            (symbol.upper(),),
        )
        rows = cur.fetchall()

    if not rows:
        raise RuntimeError(f"No cached OHLCV rows found for {symbol}")

    timestamps = [int(item[0]) for item in rows]
    closes = [float(item[1]) for item in rows]

    x = np.arange(len(closes))

    fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
    ax.plot(x, closes, color="#00d4ff", linewidth=1.6)
    ax.set_facecolor("#111827")
    fig.patch.set_facecolor("#0b1220")
    ax.grid(color="#374151", alpha=0.35, linewidth=0.6)
    ax.tick_params(colors="#d1d5db")
    ax.set_title(f"{symbol.upper()} 1h Close (cached OHLCV fallback)", color="#e5e7eb", fontsize=12, weight="bold")
    ax.set_xlabel("Candles", color="#9ca3af")
    ax.set_ylabel("Price", color="#9ca3af")

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()


def main() -> None:
    symbol = "PI"
    coin = _load_active_coin(symbol)
    if coin is None:
        coin = {
            "symbol": symbol,
            "name": "Pi",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 0.0,
            "slug": "pi-network",
        }

    if not settings.chart_img_api_key:
        raise RuntimeError("CHART_IMG_API_KEY is not configured")

    chart_client = ChartIMGClient(settings.chart_img_api_key)
    chart_bytes = chart_client.get_chart(coin_symbol=symbol, exchange="mexc", interval="1D", width=1200, height=600)
    if not chart_bytes:
        chart_bytes = _build_fallback_chart_from_cache(symbol)

    rows, headers = _build_rows(symbol)
    output_path = settings.base_dir / "docs" / "sample_notification_cell_table.png"
    title = f"{coin['symbol']} ({coin['name']}) • Sample Notification Layout"
    _compose_image(chart_bytes, rows, headers, output_path, title)

    if not settings.telegram:
        print(f"Sample image generated (Telegram not configured): {output_path}")
        return

    telegram = TelegramClient(settings.telegram["bot_token"], settings.telegram["chat_id"])
    caption = (
        "🧪 Sample layout preview\n"
        "Chart + bordered-cell strategy table\n"
        "(This is a design mock for notification format testing.)"
    )

    with output_path.open("rb") as image_file:
        message_id = telegram.send_photo(io.BytesIO(image_file.read()), caption=caption)

    print(f"Sample image generated: {output_path}")
    if message_id:
        print(f"Telegram sample sent, message_id={message_id}")
    else:
        print("Failed to send Telegram sample")


if __name__ == "__main__":
    main()
