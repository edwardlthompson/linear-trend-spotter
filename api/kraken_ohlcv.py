"""Kraken public OHLCV client for backtesting data ingestion."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

import requests


class KrakenOHLCVClient:
    """Fetches 1h OHLCV candles from Kraken public REST endpoints."""

    BASE_URL = "https://api.kraken.com/0/public"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Linear-Trend-Spotter/1.0"})
        self._last_call = 0.0
        self._pair_map: Optional[Dict[str, str]] = None

    def _throttle(self) -> None:
        min_interval = 1.1
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call = time.time()

    @staticmethod
    def _normalize_base_symbol(symbol: str) -> str:
        raw = symbol.upper().strip()
        aliases = {
            "BTC": "XBT",
        }
        return aliases.get(raw, raw)

    @staticmethod
    def _normalize_kraken_asset(asset: str) -> str:
        cleaned = asset.upper().strip()
        prefixes = ("X", "Z")
        if len(cleaned) > 3 and cleaned[0] in prefixes:
            candidate = cleaned[1:]
            if len(candidate) in (3, 4):
                cleaned = candidate
        return cleaned

    def _make_request(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        self._throttle()
        url = f"{self.BASE_URL}/{path}"
        try:
            response = self.session.get(url, params=params or {}, timeout=20)
            if response.status_code != 200:
                return None
            payload = response.json()
            if payload.get("error"):
                return None
            return payload
        except Exception:
            return None

    def _build_pair_map(self) -> Dict[str, str]:
        payload = self._make_request("AssetPairs")
        if not payload:
            return {}

        data = payload.get("result", {})
        mapping: Dict[str, str] = {}

        for pair_id, details in data.items():
            if not isinstance(details, dict):
                continue

            ws_name = details.get("wsname", "")
            alt_name = details.get("altname", "")

            quote = ""
            base = ""
            if ws_name and "/" in ws_name:
                base, quote = ws_name.split("/", 1)
                base = self._normalize_kraken_asset(base)
                quote = self._normalize_kraken_asset(quote)
            else:
                base = self._normalize_kraken_asset(str(details.get("base", "")))
                quote = self._normalize_kraken_asset(str(details.get("quote", "")))

            if quote != "USD":
                continue

            if not base:
                continue

            if base not in mapping:
                mapping[base] = alt_name or pair_id

        return mapping

    def get_usd_pair(self, symbol: str) -> Optional[str]:
        if self._pair_map is None:
            self._pair_map = self._build_pair_map()

        if not self._pair_map:
            return None

        normalized = self._normalize_base_symbol(symbol)
        if normalized in self._pair_map:
            return self._pair_map[normalized]

        # fallback exact (for already-normalized symbols)
        return self._pair_map.get(symbol.upper())

    def get_hourly_ohlcv(self, symbol: str, min_points: int = 600) -> Optional[List[dict]]:
        pair = self.get_usd_pair(symbol)
        if not pair:
            return None

        payload = self._make_request("OHLC", {"pair": pair, "interval": 60})
        if not payload:
            return None

        result = payload.get("result", {})
        candles = result.get(pair)
        if candles is None:
            for key, value in result.items():
                if key != "last" and isinstance(value, list):
                    candles = value
                    break

        if not candles or len(candles) < min_points:
            return None

        rows: List[dict] = []
        for item in candles:
            if not isinstance(item, list) or len(item) < 7:
                continue
            rows.append(
                {
                    "ts": int(item[0]),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[6]),
                }
            )

        rows.sort(key=lambda r: r["ts"])
        return rows
