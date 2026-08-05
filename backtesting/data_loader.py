"""OHLCV data loading, caching, validation, and resampling for backtesting."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import pandas as pd

from api.coingecko import CoinGeckoClient
from api.price_history_fallback import PriceHistoryFallbackClient
from database.cache import PriceCache
from utils.provider_circuit import circuit_from_settings
from utils.provider_rate_limit import MinIntervalGate

from .params import BacktestLoaderParams, loader_params_from_settings


@dataclass
class LoadResult:
    symbol: str
    timeframe: str
    source: str
    frame: Optional[pd.DataFrame]
    skip_reason: Optional[str] = None


class BacktestDataLoader:
    """Loads 1h OHLCV: CoinGecko first, then Polygon, then CoinMarketCap (when configured)."""

    def __init__(
        self,
        cache: PriceCache,
        max_cache_age_hours: int = 6,
        *,
        loader_params: BacktestLoaderParams | None = None,
    ):
        self._lp = loader_params if loader_params is not None else loader_params_from_settings()
        self.cache = cache
        self.coingecko = CoinGeckoClient(calls_per_minute=self._lp.coingecko_calls_per_minute)
        cmc_gate = MinIntervalGate(self._lp.cmc_calls_per_minute)
        poly_gate = MinIntervalGate(self._lp.polygon_calls_per_minute)
        try:
            from config.settings import settings as _settings

            _poly_c = circuit_from_settings(_settings, "polygon")
            _cmc_c = circuit_from_settings(_settings, "cmc_ohlcv_fallback")
        except Exception:
            _poly_c = _cmc_c = None
        self.price_fallback = PriceHistoryFallbackClient(
            polygon_api_key=os.getenv("POLYGON_API_KEY", ""),
            cmc_api_key=self._lp.cmc_api_key or "",
            cmc_rate_gate=cmc_gate,
            polygon_rate_gate=poly_gate,
            cmc_calls_per_minute=self._lp.cmc_calls_per_minute,
            polygon_calls_per_minute=self._lp.polygon_calls_per_minute,
            polygon_circuit=_poly_c,
            cmc_circuit=_cmc_c,
        )
        self.max_cache_age_hours = max_cache_age_hours
        self.ram_cache: OrderedDict[str, LoadResult] = OrderedDict()
        self.max_ram_cache_size = 50  # Cap at 50 to fit safely within Render's 512MB limit

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

    def _hourly_min_bars_threshold(self, days: int) -> int:
        """Minimum 1h rows required (legacy default: max(24 * days - 12, 600))."""
        per = self._lp.ohlcv_min_1h_bars_per_day
        slack = self._lp.ohlcv_min_1h_bars_slack
        floor = self._lp.ohlcv_min_1h_bars_floor
        return max(per * int(days) - int(slack), int(floor))

    def _daily_min_bars_threshold(self, days: int) -> int:
        """Minimum daily rows required (legacy default: max(days - 2, 25))."""
        return max(int(days) - int(self._lp.ohlcv_min_1d_bars_slack), int(self._lp.ohlcv_min_1d_bars_floor))

    def _get_or_fetch_1h(
        self,
        symbol: str,
        gecko_id: Optional[str],
        days: int = 30,
        *,
        cmc_id: Optional[int] = None,
    ) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
        expected_points = self._hourly_min_bars_threshold(days)

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
        if polygon_rows:
            cached = self.cache.cache_ohlcv_rows("polygon", symbol, "1h", polygon_rows, source="polygon_api")
            if cached > 0:
                frame = self._rows_to_frame(polygon_rows)
                ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1h")
                if ok and len(frame) >= expected_points:
                    return frame, "polygon_api", None

        found_cmc, cached_cmc_rows = self.cache.get_ohlcv_rows(
            "cmc",
            symbol,
            "1h",
            max_age_hours=self.max_cache_age_hours,
        )
        if found_cmc and cached_cmc_rows:
            frame = self._rows_to_frame(cached_cmc_rows)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1h")
            if ok and len(frame) >= expected_points:
                return frame, "cache", None

        cmc_rows = self.price_fallback.get_cmc_hourly_ohlcv(symbol, days=days, cmc_id=cmc_id)
        if cmc_rows:
            cached = self.cache.cache_ohlcv_rows("cmc", symbol, "1h", cmc_rows, source="cmc_api")
            if cached <= 0:
                return None, "none", "cache_write_failed"
            frame = self._rows_to_frame(cmc_rows)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1h")
            if not ok:
                return None, "cmc_api", reason
            if len(frame) < expected_points:
                return None, "cmc_api", "insufficient_hourly_bars"
            return frame, "cmc_api", None

        return None, "none", "no_intraday_ohlcv"

    def _get_or_fetch_1d_coingecko(
        self,
        symbol: str,
        gecko_id: Optional[str],
        days: int = 30,
        *,
        cmc_id: Optional[int] = None,
    ) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
        expected_points = self._daily_min_bars_threshold(days)

        found, cached_rows = self.cache.get_ohlcv_rows("coingecko", symbol, "1d", max_age_hours=self.max_cache_age_hours)
        if found and cached_rows:
            frame = self._rows_to_frame_daily(cached_rows)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1d")
            if ok and len(frame) >= expected_points:
                return frame, "cache", None

        if gecko_id:
            ohlc_rows = self.coingecko.get_ohlc(coin_id=gecko_id, days=max(30, days))
            if ohlc_rows:
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

        found_poly_d, cached_poly_d = self.cache.get_ohlcv_rows(
            "polygon",
            symbol,
            "1d",
            max_age_hours=self.max_cache_age_hours,
        )
        if found_poly_d and cached_poly_d:
            frame = self._rows_to_frame_daily(cached_poly_d)
            ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1d")
            if ok and len(frame) >= expected_points:
                return frame, "cache", None

        polygon_daily = self.price_fallback.get_polygon_30d_daily_ohlcv(symbol)
        if polygon_daily:
            cached = self.cache.cache_ohlcv_rows("polygon", symbol, "1d", polygon_daily, source="polygon_api")
            if cached > 0:
                frame = self._rows_to_frame_daily(polygon_daily)
                ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1d")
                if ok and len(frame) >= expected_points:
                    return frame, "polygon_api", None

        daily_prices = self.price_fallback.get_cmc_daily_closes(symbol, cmc_id=cmc_id)
        if daily_prices and len(daily_prices) >= expected_points:
            end_d = datetime.now(timezone.utc).date()
            synthetic: list[dict] = []
            n = len(daily_prices)
            for i, price in enumerate(daily_prices):
                d = end_d - timedelta(days=(n - 1 - i))
                ts_sec = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
                p = float(price)
                synthetic.append(
                    {"ts": ts_sec, "open": p, "high": p, "low": p, "close": p, "volume": 1.0}
                )
            cached = self.cache.cache_ohlcv_rows("cmc", symbol, "1d", synthetic, source="cmc_api")
            if cached > 0:
                frame = self._rows_to_frame_daily(synthetic)
                ok, reason = self.validate_ohlcv_frame(frame, expected_timeframe="1d")
                if ok and len(frame) >= expected_points:
                    return frame, "cmc_api", None

        return None, "none", "no_coingecko_ohlc"

    def load(
        self,
        symbol: str,
        timeframe: str = "1h",
        days: int = 30,
        gecko_id: Optional[str] = None,
        cmc_id: Optional[int] = None,
    ) -> LoadResult:
        cache_key = f"{symbol}_{timeframe}_{days}_{gecko_id or ''}_{cmc_id or ''}"
        if cache_key in self.ram_cache:
            self.ram_cache.move_to_end(cache_key)
            return self.ram_cache[cache_key]
        
        res = self._load_internal(symbol, timeframe, days, gecko_id, cmc_id=cmc_id)
        
        self.ram_cache[cache_key] = res
        if len(self.ram_cache) > self.max_ram_cache_size:
            self.ram_cache.popitem(last=False)
            
        return res

    def _load_internal(
        self,
        symbol: str,
        timeframe: str = "1h",
        days: int = 30,
        gecko_id: Optional[str] = None,
        *,
        cmc_id: Optional[int] = None,
    ) -> LoadResult:
        frame_1h, source, reason = self._get_or_fetch_1h(
            symbol=symbol, gecko_id=gecko_id, days=days, cmc_id=cmc_id
        )

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
                cmc_id=cmc_id,
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
