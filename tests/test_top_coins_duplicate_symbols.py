"""Regression: duplicate provider tickers must keep the best market-cap rank."""

from __future__ import annotations

from typing import Any

from scanner.top_coins_stage import fetch_top_coins_dataset


class _FakeLogger:
    def info(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def error(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeMetrics:
    def increment(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeGecko:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def get_top_coins_with_gains(self, limit: int = 250) -> list[dict[str, Any]]:
        return self._rows[:limit]


class _FakeCmc:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def get_all_coins_with_gains(self, limit: int = 250) -> list[dict[str, Any]]:
        return self._rows[:limit]

    def extract_gains(self, row: dict[str, Any]) -> dict[str, float]:
        return {
            "7d": float(row.get("g7", 0) or 0),
            "30d": float(row.get("g30", 0) or 0),
            "60d": 0.0,
            "90d": 0.0,
        }

    def extract_coin_data(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": str(row.get("symbol", "")).upper(),
            "name": str(row.get("name", "")),
            "slug": str(row.get("slug", "")),
            "rank": int(row.get("cmc_rank") or 0),
            "price": float(row.get("price", 0) or 0),
            "volume_24h": float(row.get("volume_24h", 0) or 0),
        }


def test_coingecko_duplicate_symbols_keep_best_rank() -> None:
    rows = [
        {
            "symbol": "rain",
            "id": "rain",
            "name": "Rain",
            "market_cap_rank": 13,
            "current_price": 1.0,
            "total_volume": 50_000_000,
            "price_change_percentage_7d_in_currency": 12.0,
            "price_change_percentage_30d_in_currency": 40.0,
        },
        {
            "symbol": "btc",
            "id": "bitcoin",
            "name": "Bitcoin",
            "market_cap_rank": 1,
            "current_price": 100.0,
            "total_volume": 1_000_000_000,
            "price_change_percentage_7d_in_currency": 1.0,
            "price_change_percentage_30d_in_currency": 2.0,
        },
        {
            "symbol": "rain",
            "id": "rainmaker",
            "name": "Rainmaker",
            "market_cap_rank": 1610,
            "current_price": 0.01,
            "total_volume": 1000,
            "price_change_percentage_7d_in_currency": 90.0,
            "price_change_percentage_30d_in_currency": 200.0,
        },
    ]
    dataset = fetch_top_coins_dataset(
        top_coins_provider="coingecko",
        top_coins_limit=4000,
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gecko=_FakeGecko(rows),
        cmc=_FakeCmc([]),
        app_logger=_FakeLogger(),
        metrics=_FakeMetrics(),
    )
    assert dataset is not None
    rain = dataset.cmc_by_symbol["RAIN"]
    assert rain["info"]["name"] == "Rain"
    assert rain["info"]["gecko_id"] == "rain"
    assert rain["info"]["volume_24h"] == 50_000_000
    assert rain["gains"]["7d"] == 12.0
    assert len(dataset.all_cmc_coins) == 3
    assert len(dataset.cmc_by_symbol) == 2


def test_cmc_duplicate_symbols_keep_best_rank_even_if_out_of_order() -> None:
    rows = [
        {
            "symbol": "FUN",
            "name": "FunClone",
            "slug": "fun-clone",
            "cmc_rank": 2200,
            "price": 0.01,
            "volume_24h": 500,
            "g7": 80.0,
            "g30": 120.0,
        },
        {
            "symbol": "FUN",
            "name": "FUNToken",
            "slug": "funtoken",
            "cmc_rank": 250,
            "price": 0.05,
            "volume_24h": 5_000_000,
            "g7": 10.0,
            "g30": 25.0,
        },
    ]
    dataset = fetch_top_coins_dataset(
        top_coins_provider="cmc",
        top_coins_limit=4000,
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gecko=_FakeGecko([]),
        cmc=_FakeCmc(rows),
        app_logger=_FakeLogger(),
        metrics=_FakeMetrics(),
    )
    assert dataset is not None
    fun = dataset.cmc_by_symbol["FUN"]
    assert fun["info"]["name"] == "FUNToken"
    assert fun["info"]["slug"] == "funtoken"
    assert fun["info"]["rank"] == 250
    assert fun["gains"]["7d"] == 10.0
