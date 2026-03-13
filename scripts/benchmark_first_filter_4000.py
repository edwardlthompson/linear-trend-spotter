#!/usr/bin/env python3
"""Quick benchmark: first filter speed for top-N CMC vs CoinGecko."""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.coinmarketcap import CoinMarketCapClient
from config.constants import STABLECOINS
from config.settings import settings


@dataclass
class BenchResult:
    source: str
    requested_top: int
    fetched: int
    passed_filter: int
    fetch_seconds: float
    filter_seconds: float

    @property
    def total_seconds(self) -> float:
        return self.fetch_seconds + self.filter_seconds


def _passes_first_filter(symbol: str, volume_24h: float, gain_7d: float, gain_30d: float) -> bool:
    if symbol in STABLECOINS:
        return False
    if volume_24h < settings.min_volume:
        return False
    if not (gain_7d > 7 and gain_30d > 30 and gain_30d > gain_7d):
        return False
    return True


def benchmark_cmc(top_n: int) -> BenchResult:
    client = CoinMarketCapClient(settings.cmc_api_key)

    started = time.perf_counter()
    coins = client.get_all_coins_with_gains(limit=top_n) or []
    fetch_elapsed = time.perf_counter() - started

    filter_start = time.perf_counter()
    passed = 0
    for coin in coins:
        symbol = str(coin.get("symbol", "")).upper()
        usd = coin.get("quote", {}).get("USD", {})
        volume = float(usd.get("volume_24h", 0) or 0)
        gain_7d = float(usd.get("percent_change_7d", 0) or 0)
        gain_30d = float(usd.get("percent_change_30d", 0) or 0)
        if _passes_first_filter(symbol, volume, gain_7d, gain_30d):
            passed += 1
    filter_elapsed = time.perf_counter() - filter_start

    return BenchResult(
        source="CMC",
        requested_top=top_n,
        fetched=len(coins),
        passed_filter=passed,
        fetch_seconds=fetch_elapsed,
        filter_seconds=filter_elapsed,
    )


def _coingecko_session() -> tuple[requests.Session, str]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Linear-Trend-Spotter/1.0"})

    api_key = os.getenv("COINGECKO_API_KEY", "").strip()
    if api_key and api_key.startswith("CG-"):
        session.headers["x-cg-demo-api-key"] = api_key
        base_url = "https://api.coingecko.com/api/v3"
    elif api_key:
        session.headers["x-cg-pro-api-key"] = api_key
        base_url = "https://pro-api.coingecko.com/api/v3"
    else:
        base_url = "https://api.coingecko.com/api/v3"

    return session, base_url


def benchmark_coingecko(top_n: int) -> BenchResult:
    session, base_url = _coingecko_session()
    per_page = 250
    pages = int(math.ceil(top_n / per_page))

    coins: List[Dict] = []
    fetch_start = time.perf_counter()

    for page in range(1, pages + 1):
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "7d,30d",
        }
        resp = session.get(f"{base_url}/coins/markets", params=params, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"CoinGecko /coins/markets failed on page {page}: {resp.status_code} {resp.text[:180]}")
        page_rows = resp.json()
        if not isinstance(page_rows, list):
            raise RuntimeError(f"CoinGecko response on page {page} is not a list")
        coins.extend(page_rows)
        # Small pacing for public endpoint stability, still fast.
        if page < pages:
            time.sleep(0.12)

    coins = coins[:top_n]
    fetch_elapsed = time.perf_counter() - fetch_start

    filter_start = time.perf_counter()
    passed = 0
    for coin in coins:
        symbol = str(coin.get("symbol", "")).upper()
        volume = float(coin.get("total_volume", 0) or 0)
        gain_7d = float(coin.get("price_change_percentage_7d_in_currency", 0) or 0)
        gain_30d = float(coin.get("price_change_percentage_30d_in_currency", 0) or 0)
        if _passes_first_filter(symbol, volume, gain_7d, gain_30d):
            passed += 1
    filter_elapsed = time.perf_counter() - filter_start

    return BenchResult(
        source="CoinGecko",
        requested_top=top_n,
        fetched=len(coins),
        passed_filter=passed,
        fetch_seconds=fetch_elapsed,
        filter_seconds=filter_elapsed,
    )


def _print_result(result: BenchResult) -> None:
    print(
        f"{result.source:10} | fetched={result.fetched:4d}/{result.requested_top} | "
        f"passed={result.passed_filter:4d} | fetch={result.fetch_seconds:7.3f}s | "
        f"filter={result.filter_seconds:7.3f}s | total={result.total_seconds:7.3f}s"
    )


def main() -> None:
    top_n = 4000
    print(f"Benchmarking first filter for top {top_n} coins...")
    print(f"Filter thresholds: volume>={settings.min_volume}, 7d>7, 30d>30, 30d>7d")

    if not settings.cmc_api_key:
        raise RuntimeError("CMC_API_KEY is missing in environment; cannot benchmark CMC")

    cmc_result = benchmark_cmc(top_n)
    cg_result = benchmark_coingecko(top_n)

    print("\nResults:")
    _print_result(cmc_result)
    _print_result(cg_result)

    delta = cg_result.total_seconds - cmc_result.total_seconds
    if delta > 0:
        print(f"\nCoinGecko slower by {delta:.3f}s for first-filter stage.")
    else:
        print(f"\nCoinGecko faster by {abs(delta):.3f}s for first-filter stage.")


if __name__ == "__main__":
    main()
