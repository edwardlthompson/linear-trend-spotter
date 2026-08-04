"""Regression: ambiguous ticker mappings must not guess via rowid / GROUP BY."""

from __future__ import annotations

import tempfile
from pathlib import Path

from api.coingecko_mapper import CoinGeckoMapper


def _insert_mappings(mapper: CoinGeckoMapper, rows: list[tuple[str, str, str]]) -> None:
    conn = mapper._get_connection()
    for symbol, cg_id, name in rows:
        conn.execute(
            """
            INSERT INTO symbol_mapping (symbol, coingecko_id, name, last_updated)
            VALUES (?, ?, ?, ?)
            """,
            (symbol, cg_id, name, "2025-01-01"),
        )
    conn.commit()


def test_get_coin_id_refuses_ambiguous_ticker_without_unique_row() -> None:
    """Live /coins/list order puts batcat before bitcoin for symbol BTC — never guess."""
    with tempfile.TemporaryDirectory() as td:
        m = CoinGeckoMapper(Path(td) / "map.sqlite")
        _insert_mappings(
            m,
            [
                ("BTC", "batcat", "batcat"),
                ("BTC", "bitcoin", "Bitcoin"),
                ("ETH", "anubis-bridged-eth-anubis", "Anubis Bridged ETH"),
                ("ETH", "ethereum", "Ethereum"),
                ("UNIQ", "only-one", "Unique Coin"),
            ],
        )

        assert m.get_coin_id("BTC") is None
        assert m.get_coin_id("ETH") is None
        assert m.get_coin_id("UNIQ") == "only-one"
        assert m.get_coin_id_with_name_hint("BTC", "Bitcoin") == "bitcoin"
        assert m.get_coin_id_with_name_hint("BTC", None) is None
        assert m.get_coin_id_with_name_hint("ETH", "Ethereum") == "ethereum"
        m.close()


def test_get_coin_ids_batch_skips_ambiguous_symbols() -> None:
    with tempfile.TemporaryDirectory() as td:
        m = CoinGeckoMapper(Path(td) / "map.sqlite")
        _insert_mappings(
            m,
            [
                ("BTC", "batcat", "batcat"),
                ("BTC", "bitcoin", "Bitcoin"),
                ("AAA", "aaa-id", "AAA"),
            ],
        )
        batch = m.get_coin_ids_batch(["BTC", "AAA", "MISSING"])
        assert batch == {"AAA": "aaa-id"}
        m.close()


def test_name_hint_requires_unique_name_match() -> None:
    with tempfile.TemporaryDirectory() as td:
        m = CoinGeckoMapper(Path(td) / "map.sqlite")
        _insert_mappings(
            m,
            [
                ("DUP", "dup-a", "Same Name"),
                ("DUP", "dup-b", "Same Name"),
            ],
        )
        assert m.get_coin_id_with_name_hint("DUP", "Same Name") is None
        m.close()
