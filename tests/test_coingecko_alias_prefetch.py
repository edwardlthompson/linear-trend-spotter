"""Batched CoinGecko /coins/markets alias prefetch."""

from __future__ import annotations

from unittest.mock import MagicMock

from scanner.coingecko_alias_prefetch import (
    prefetch_alias_markets_by_gecko_id,
    top_up_alias_markets_for_symbols,
)


def test_prefetch_includes_all_config_alias_targets() -> None:
    gecko = MagicMock()
    gecko.get_markets_rows_for_ids.return_value = {"a": {"id": "a"}, "b": {"id": "b"}}

    log = MagicMock()
    aliases = {"ZZZ1": "alpha", "ZZZ2": "beta"}
    all_symbols: list[str] = []

    prefetch_alias_markets_by_gecko_id(
        top_coins_provider="coingecko",
        coingecko_id_aliases=aliases,
        all_symbols=all_symbols,
        gecko=gecko,
        app_logger=log,
    )

    gecko.get_markets_rows_for_ids.assert_called_once()
    ids_arg = gecko.get_markets_rows_for_ids.call_args[0][0]
    assert set(ids_arg) == {"alpha", "beta"}


def test_top_up_fetches_only_missing_ids() -> None:
    gecko = MagicMock()
    gecko.get_markets_rows_for_ids.return_value = {"gamma": {"id": "gamma"}}
    log = MagicMock()
    by_id: dict[str, dict] = {"alpha": {"id": "alpha"}}
    aliases = {"X": "gamma"}
    top_up_alias_markets_for_symbols(
        top_coins_provider="coingecko",
        coingecko_id_aliases=aliases,
        all_symbols=["X"],
        alias_markets_by_id=by_id,
        gecko=gecko,
        app_logger=log,
    )
    gecko.get_markets_rows_for_ids.assert_called_once_with(["gamma"])
    assert "gamma" in by_id
