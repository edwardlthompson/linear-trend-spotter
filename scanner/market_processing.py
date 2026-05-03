"""Market-data helper transforms used by scanner pipeline (Milestone I2 extraction)."""

from __future__ import annotations


def _ticker_matches_target(target: str, exchange_id: str, exchange_name: str) -> bool:
    if target in exchange_id or target in exchange_name:
        return True
    # CoinGecko ticker `market.identifier` for Coinbase is still "gdax".
    if target == "coinbase" and exchange_id == "gdax":
        return True
    return False


def process_tickers(tickers_data, target_exchanges):
    """Process ticker data to extract exchange volumes."""
    volumes = {ex: "N/A" for ex in target_exchanges}

    if not tickers_data or "tickers" not in tickers_data:
        return volumes

    for ticker in tickers_data.get("tickers", []):
        exchange_id = ticker.get("market", {}).get("identifier", "").lower()
        exchange_name = ticker.get("market", {}).get("name", "").lower()
        volume = float(ticker.get("converted_volume", {}).get("usd", 0))

        for target in target_exchanges:
            if _ticker_matches_target(target, exchange_id, exchange_name):
                if volumes[target] == "N/A" or volume > volumes[target]:
                    volumes[target] = volume

    return volumes


def aggregate_daily_bars_from_hourly(hourly_rows):
    """Aggregate hourly OHLCV rows into daily bars for OHLCV uniformity scoring."""
    buckets = {}
    for row in hourly_rows:
        ts = int(row["ts"])
        day_key = ts // 86400
        buckets.setdefault(day_key, []).append(row)

    daily_bars = []
    for day_key in sorted(buckets.keys()):
        day_rows = sorted(buckets[day_key], key=lambda item: int(item["ts"]))
        if not day_rows:
            continue
        daily_bars.append(
            {
                "open": float(day_rows[0]["open"]),
                "high": max(float(item["high"]) for item in day_rows),
                "low": min(float(item["low"]) for item in day_rows),
                "close": float(day_rows[-1]["close"]),
                "volume": sum(float(item.get("volume", 0.0) or 0.0) for item in day_rows),
            }
        )

    return daily_bars
