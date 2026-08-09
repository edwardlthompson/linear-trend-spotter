"""OHLCV cache must key CoinGecko series by coin id, not ticker."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from scanner.uniformity_stages import _fetch_hourly_ohlcv_for_uniformity


def _load_price_cache_class():
    """Load PriceCache without importing config.settings (dotenv may be absent)."""
    path = Path(__file__).resolve().parents[1] / "database" / "cache.py"
    spec = importlib.util.spec_from_file_location("price_cache_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PriceCache, mod.ohlcv_cache_symbol_key


def test_ohlcv_cache_symbol_key_coingecko_requires_asset_id():
    _, key_fn = _load_price_cache_class()
    assert key_fn("coingecko", "RAIN", asset_id="rain") == "rain"
    assert key_fn("coingecko", "RAIN", asset_id=None) is None
    assert key_fn("cmc", "RAIN", asset_id="123") == "id:123"
    assert key_fn("cmc", "RAIN", asset_id=None) == "RAIN"
    assert key_fn("polygon", "RAIN") == "RAIN"


def test_coingecko_cache_does_not_reuse_candles_across_remapped_tickers(tmp_path: Path):
    PriceCache, _ = _load_price_cache_class()
    cache = PriceCache(tmp_path / "scanner.db")

    rain_rows = [
        {
            "ts": 1_700_000_000 + i * 3600,
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.0 + i,
            "volume": 1.0,
        }
        for i in range(5)
    ]
    clone_rows = [
        {
            "ts": 1_700_000_000 + i * 3600,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 100.0 + i,
            "volume": 1.0,
        }
        for i in range(5)
    ]

    written = cache.cache_ohlcv_rows(
        "coingecko",
        "RAIN",
        "1h",
        rain_rows,
        source="coingecko_api",
        asset_id="rain",
    )
    assert written == 5

    # Same ticker, different CoinGecko id must miss — not reuse rain candles.
    found_clone, clone_cached = cache.get_ohlcv_rows(
        "coingecko",
        "RAIN",
        "1h",
        max_age_hours=12,
        asset_id="rainmaker",
    )
    assert found_clone is False
    assert clone_cached is None

    cache.cache_ohlcv_rows(
        "coingecko",
        "RAIN",
        "1h",
        clone_rows,
        source="coingecko_api",
        asset_id="rainmaker",
    )
    found_rain, rain_cached = cache.get_ohlcv_rows(
        "coingecko",
        "RAIN",
        "1h",
        max_age_hours=12,
        asset_id="rain",
    )
    found_clone2, clone_cached2 = cache.get_ohlcv_rows(
        "coingecko",
        "RAIN",
        "1h",
        max_age_hours=12,
        asset_id="rainmaker",
    )
    assert found_rain and rain_cached
    assert found_clone2 and clone_cached2
    assert [r["close"] for r in rain_cached] == [10.0 + i for i in range(5)]
    assert [r["close"] for r in clone_cached2] == [100.0 + i for i in range(5)]


def test_coingecko_write_without_asset_id_is_rejected(tmp_path: Path):
    PriceCache, _ = _load_price_cache_class()
    cache = PriceCache(tmp_path / "scanner.db")
    rows = [
        {
            "ts": 1_700_000_000,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 1.0,
        }
    ]
    assert cache.cache_ohlcv_rows("coingecko", "BTC", "1h", rows, source="coingecko_api") == 0
    found, cached = cache.get_ohlcv_rows("coingecko", "BTC", "1h", max_age_hours=12)
    assert found is False
    assert cached is None


class _FakeCache:
    def __init__(self) -> None:
        self.writes: list[tuple] = []

    def get_ohlcv_rows(self, exchange, symbol, timeframe, max_age_hours=6, *, asset_id=None):
        return False, None

    def cache_ohlcv_rows(
        self,
        exchange,
        symbol,
        timeframe,
        rows,
        source="x",
        *,
        asset_id=None,
    ):
        self.writes.append((exchange, symbol, asset_id, source, len(rows)))
        return len(rows)


class _FakeGecko:
    def get_hourly_ohlcv(self, cg_id, days=30):
        assert cg_id == "rain"
        return [
            {
                "ts": 1_700_000_000,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
            }
        ]


def test_uniformity_fetch_passes_coingecko_asset_id():
    cache = _FakeCache()
    rows, src = _fetch_hourly_ohlcv_for_uniformity(
        {"symbol": "RAIN", "cg_id": "rain"},
        cache=cache,
        gecko=_FakeGecko(),
        history_fallback=object(),
        cache_price_hours=12,
        uniformity_days=30,
        source_order=("coingecko",),
    )
    assert src == "coingecko_api"
    assert rows
    assert cache.writes == [("coingecko", "RAIN", "rain", "coingecko_api", 1)]


def test_sparkline_prefers_asset_id_over_legacy_ticker_rows(tmp_path: Path):
    from scanner.coin_enrichment import _hourly_closes_from_scanner_db

    PriceCache, _ = _load_price_cache_class()
    db = tmp_path / "scanner.db"
    cache = PriceCache(db)
    good = [
        {
            "ts": 1_700_000_000 + i * 3600,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": float(i + 1),
            "volume": 1.0,
        }
        for i in range(5)
    ]
    cache.cache_ohlcv_rows(
        "coingecko", "RAIN", "1h", good, source="coingecko_api", asset_id="rain"
    )
    # Legacy ticker-keyed pollution must not win when asset_id rows exist.
    import sqlite3

    with sqlite3.connect(str(db)) as conn:
        for i in range(5):
            conn.execute(
                """
                INSERT OR REPLACE INTO ohlcv_cache
                (exchange, symbol, timeframe, ts, open, high, low, close, volume, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "coingecko",
                    "RAIN",
                    "1h",
                    1_700_000_000 + i * 3600,
                    1.0,
                    1.0,
                    1.0,
                    999.0,
                    1.0,
                    "legacy",
                    "2099-01-01T00:00:00",
                ),
            )
        conn.commit()

    closes = _hourly_closes_from_scanner_db(db, "RAIN", asset_id="rain")
    assert closes == [1.0, 2.0, 3.0, 4.0, 5.0]
