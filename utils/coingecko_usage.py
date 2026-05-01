"""Milestone H0: classify CoinGecko API URLs and record per-scan HTTP counters in metrics."""

from __future__ import annotations

from urllib.parse import urlparse

from utils.metrics import metrics


def record_coingecko_http(url: str) -> None:
    """Count one successful (or attempted) CoinGecko HTTP call by endpoint family."""
    path = urlparse(str(url or "")).path.lower()
    family = _endpoint_family(path)
    metrics.increment("coingecko_http_total")
    metrics.increment(f"coingecko_http_{family}")


def _endpoint_family(path: str) -> str:
    if "/coins/markets" in path:
        return "markets"
    if "/coins/list" in path:
        return "coins_list"
    if "/market_chart" in path:
        return "market_chart"
    if "/ohlc" in path:
        return "ohlc"
    if "/tickers" in path:
        return "tickers"
    if "/simple/" in path:
        return "simple"
    if "/coins/" in path:
        rest = path.split("/coins/", 1)[-1].strip("/")
        if rest and "/" not in rest:
            return "coin_detail"
    return "other"
