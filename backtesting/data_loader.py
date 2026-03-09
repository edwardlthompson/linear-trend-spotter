"""OHLCV data loading, caching, validation, and resampling for backtesting."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional, Tuple

import pandas as pd

from api.coingecko import CoinGeckoClient
from api.price_history_fallback import PriceHistoryFallbackClient
from config.settings import settings
from database.cache import PriceCache


@dataclass
class LoadResult:
    symbol: str
    timeframe: str
    source: str
    frame: Optional[pd.DataFrame]
    skip_reason: Optional[str] = None


class BacktestDataLoader:
    """Loads CoinGecko 1h OHLCV and falls back to Polygon intraday when needed."""

    def __init__(self, cache: PriceCache, max_cache_age_hours: int = 6):
        self.cache = cache
        self.coingecko = CoinGeckoClient(calls_per_minute=settings.coingecko_calls_per_minute)
        self.price_fallback = PriceHistoryFallbackClient(
            polygon_api_key=os.getenv("POLYGON_API_KEY", ""),
            cmc_api_key="",
        )
        self.max_cache_age_hours = max_cache_age_hours

    @staticmethod
    def _rows_to_frame(rows: list[dict]) -> pd.DataFrame:
        frame = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        frame["ts"] = pd.to_datetime(frame["ts"], unit="s", utc=True)
        frame = frame.set_index("ts").sort_index()
        frame = frame[["open", "high", "low", "close", "volume"]].astype(float)
        return frame

    @staticmethod
    def _rows_to_frame_daily(rows: list[dict]) -> pd.DataFrame:
        frame = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        frame["ts"] = pd.to_datetime(frame["ts"], unit="s", utc=True)
        frame = frame.set_index("ts").sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame = frame[["open", "high", "low", "close", "volume"]].astype(float)
        return frame

    @staticmethod
    def validate_ohlcv_frame(frame: pd.DataFrame, expected_timeframe: str = "1h") -> Tuple[bool, str]:
        if frame is None or frame.empty:
            return False, "empty_frame"

        required_cols = {"open", "high", "low", "close", "volume"}
        if set(frame.columns) != required_cols:
            return False, "invalid_columns"

        if frame.index.has_duplicates:
            return False, "duplicate_timestamps"

        if not frame.index.is_monotonic_increasing:
            return False, "non_monotonic_timestamps"

        if frame.isnull().any().any():
            return False, "nan_values_present"

        if (frame[["open", "high", "low", "close"]] <= 0).any().any():
            return False, "non_positive_prices"

        if (frame["volume"] < 0).any():
            return False, "negative_volume"

        if expected_timeframe == "1h" and len(frame) > 1:
            diffs = frame.index.to_series().diff().dropna().dt.total_seconds()
            missing_steps = int((diffs != 3600).sum())
            if missing_steps > 2:
                return False, f"missing_hourly_bars:{missing_steps}"

        return True, "ok"

    @staticmethod
    def _resample(frame_1h: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        if timeframe == "1h":
            return frame_1h

        if timeframe == "4h":
            rule = "4h"
        elif timeframe in ("1d", "daily"):
            rule = "1d"
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        resampled = frame_1h.resample(rule).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        resampled = resampled.dropna(subset=["open", "high", "low", "close"])
        return resampled

    def _get_or_fetch_1h(
        self,
        symbol: str,
        gecko_id: Optional[str],
        days: int = 30,
    ) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
        expected_points = max(24 * days - 12, 600)

        found, cached_rows = self.cache.get_ohlcv_rows("coingecko", symbol, "1h", max_age_hours=self.max_cache_age_hours)
        if found and cached_rows:
            frame = self._rows_to_frame(cached_rows)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1h")
            if ok and len(frame) >= expected_points:
                return frame, "cache", None

        if gecko_id:
            api_rows = self.coingecko.get_hourly_ohlcv(gecko_id, days=max(30, days))
        else:
            api_rows = None

        if api_rows:
            cached = self.cache.cache_ohlcv_rows("coingecko", symbol, "1h", api_rows, source="coingecko_api")
            if cached <= 0:
                return None, "none", "cache_write_failed"

            frame = self._rows_to_frame(api_rows)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1h")
            if not ok:
                return None, "coingecko_api", reason

            return frame, "coingecko_api", None

        found_polygon, cached_polygon_rows = self.cache.get_ohlcv_rows(
            "polygon",
            symbol,
            "1h",
            max_age_hours=self.max_cache_age_hours,
        )
        if found_polygon and cached_polygon_rows:
            frame = self._rows_to_frame(cached_polygon_rows)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1h")
            if ok and len(frame) >= expected_points:
                return frame, "cache", None

        polygon_rows = self.price_fallback.get_polygon_30d_hourly_ohlcv(symbol)
        if not polygon_rows:
            return None, "none", "no_intraday_ohlcv"

        cached = self.cache.cache_ohlcv_rows("polygon", symbol, "1h", polygon_rows, source="polygon_api")
        if cached <= 0:
            return None, "none", "cache_write_failed"

        frame = self._rows_to_frame(polygon_rows)
        ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1h")
        if not ok:
            return None, "polygon_api", reason

        return frame, "polygon_api", None

    def _get_or_fetch_1d_coingecko(
        self,
        symbol: str,
        gecko_id: Optional[str],
        days: int = 30,
    ) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
        if not gecko_id:
            return None, "none", "missing_gecko_id"

        expected_points = max(days - 2, 25)

        found, cached_rows = self.cache.get_ohlcv_rows("coingecko", symbol, "1d", max_age_hours=self.max_cache_age_hours)
        if found and cached_rows:
            frame = self._rows_to_frame_daily(cached_rows)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1d")
            if ok and len(frame) >= expected_points:
                return frame, "cache", None

        ohlc_rows = self.coingecko.get_ohlc(coin_id=gecko_id, days=max(30, days))
        if not ohlc_rows:
            return None, "none", "no_coingecko_ohlc"

        normalized_rows: list[dict] = []
        for row in ohlc_rows:
            ts_sec = int(float(row[0]) / 1000)
            normalized_rows.append(
                {
                    "ts": ts_sec,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": 1.0,
                }
            )

        cached = self.cache.cache_ohlcv_rows("coingecko", symbol, "1d", normalized_rows, source="coingecko_api")
        if cached <= 0:
            return None, "none", "cache_write_failed"

        frame = self._rows_to_frame_daily(normalized_rows)
        ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1d")
        if not ok:
            return None, "coingecko_api", reason
        if len(frame) < expected_points:
            return None, "coingecko_api", "insufficient_daily_bars"

        return frame, "coingecko_api", None

    def load(self, symbol: str, timeframe: str = "1h", days: int = 30, gecko_id: Optional[str] = None) -> LoadResult:
        frame_1h, source, reason = self._get_or_fetch_1h(symbol=symbol, gecko_id=gecko_id, days=days)

        if frame_1h is None:
            if timeframe != "1d":
                return LoadResult(
                    symbol=symbol,
                    timeframe=timeframe,
                    source=source,
                    frame=None,
                    skip_reason=reason or "no_hourly_ohlcv",
                )

            frame_1d, daily_source, daily_reason = self._get_or_fetch_1d_coingecko(
                symbol=symbol,
                gecko_id=gecko_id,
                days=days,
            )
            if frame_1d is None:
                return LoadResult(symbol=symbol, timeframe=timeframe, source=daily_source, frame=None, skip_reason=daily_reason)
            return LoadResult(symbol=symbol, timeframe=timeframe, source=daily_source, frame=frame_1d, skip_reason=None)

        try:
            frame = self._resample(frame_1h, timeframe)
        except Exception as exc:
            return LoadResult(
                symbol=symbol,
                timeframe=timeframe,
                source=source,
                frame=None,
                skip_reason=f"resample_error:{exc}",
            )

        if frame.empty:
            return LoadResult(symbol=symbol, timeframe=timeframe, source=source, frame=None, skip_reason="empty_after_resample")

        return LoadResult(symbol=symbol, timeframe=timeframe, source=source, frame=frame, skip_reason=None)
