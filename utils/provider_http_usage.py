"""Count Polygon and CoinMarketCap HTTP calls into metrics (J3 scan cost dashboard)."""

from __future__ import annotations

from urllib.parse import urlparse

from utils.metrics import metrics


def record_polygon_http(url: str) -> None:
    path = urlparse(str(url or "")).path.lower()
    metrics.increment("polygon_http_total")
    if "/aggs/" in path:
        metrics.increment("polygon_http_aggs")
    else:
        metrics.increment("polygon_http_other")


def record_cmc_http(url: str) -> None:
    path = urlparse(str(url or "")).path.lower()
    metrics.increment("cmc_http_total")
    if "ohlcv" in path or "quotes/historical" in path:
        metrics.increment("cmc_http_ohlcv")
    elif "listings" in path:
        metrics.increment("cmc_http_listings")
    else:
        metrics.increment("cmc_http_other")
