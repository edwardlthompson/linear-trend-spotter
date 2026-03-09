"""Send sample Telegram notification with separate chart and strategy-table images."""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.chart_img import ChartIMGClient
from backtesting.report import notification_rows_for_symbol
from config.settings import settings
from notifications.formatter import MessageFormatter
from notifications.image_renderer import build_fallback_chart_image, build_combined_notification_image
from notifications.telegram import TelegramClient


def _load_coin(symbol: str) -> dict:
    db_path = settings.db_paths["scanner"]
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT coin_symbol, coin_name, gain_7d, gain_30d, uniformity_score, slug
            FROM active_coins
            WHERE coin_symbol = ?
            """,
            (symbol.upper(),),
        )
        row = cursor.fetchone()

    if not row:
        return {
            "symbol": symbol.upper(),
            "name": symbol.upper(),
            "slug": symbol.lower(),
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 0.0,
            "volume_24h": 0.0,
            "exchange_volumes": {},
            "listed_on": ["mexc", "coinbase", "kraken"],
        }

    return {
        "symbol": row[0],
        "name": row[1],
        "slug": row[5] or row[0].lower(),
        "gains": {"7d": float(row[2] or 0.0), "30d": float(row[3] or 0.0)},
        "uniformity_score": float(row[4] or 0.0),
        "volume_24h": 0.0,
        "exchange_volumes": {},
        "listed_on": ["mexc", "coinbase", "kraken"],
    }


def _attach_backtest_rows(coin: dict) -> dict:
    artifact = settings.base_dir / "backtest_results.json"
    if not artifact.exists():
        coin["backtest_top_strategies"] = []
        coin["backtest_buy_hold"] = None
        return coin

    summary = json.loads(artifact.read_text(encoding="utf-8"))
    details = notification_rows_for_symbol(summary, coin["symbol"], top_n=5)
    coin["backtest_top_strategies"] = details.get("top_strategies", [])
    coin["backtest_buy_hold"] = details.get("buy_hold")
    return coin


def main() -> None:
    if not settings.telegram:
        raise RuntimeError("Telegram is not configured")

    symbol = "PI"
    coin = _attach_backtest_rows(_load_coin(symbol))

    chart_bytes = None
    if settings.chart_img_api_key:
        chart_client = ChartIMGClient(settings.chart_img_api_key)
        try:
            chart_bytes = chart_client.get_chart(coin_symbol=coin["symbol"], exchange="mexc", interval="1D", width=900, height=420)
        except Exception:
            chart_bytes = None

    if not chart_bytes:
        chart_bytes = build_fallback_chart_image(coin["symbol"], settings.db_paths["scanner"])

    combined_bytes = build_combined_notification_image(coin, chart_bytes) if chart_bytes else None

    telegram = TelegramClient(settings.telegram["bot_token"], settings.telegram["chat_id"])

    caption = MessageFormatter.format_entry(coin)
    message_id = None
    if chart_bytes:
        payload = combined_bytes if combined_bytes else chart_bytes
        message_id = telegram.send_photo(io.BytesIO(payload), caption=caption)
    else:
        message_id = telegram.send_message(caption)

    print(f"message_id={message_id}")


if __name__ == "__main__":
    main()
