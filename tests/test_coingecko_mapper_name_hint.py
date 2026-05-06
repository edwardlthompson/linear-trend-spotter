"""Name-aware CoinGecko id resolution when universe comes from CMC listings."""

from __future__ import annotations

import tempfile
from pathlib import Path

from api.coingecko_mapper import CoinGeckoMapper


def test_get_coin_id_with_name_hint_disambiguates_duplicate_symbols() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "map.sqlite"
        m = CoinGeckoMapper(db)
        conn = m._get_connection()
        conn.execute(
            """
            INSERT INTO symbol_mapping (symbol, coingecko_id, name, last_updated)
            VALUES (?, ?, ?, ?), (?, ?, ?, ?)
            """,
            (
                "TEST",
                "token-a",
                "Alpha Token",
                "2025-01-01",
                "TEST",
                "token-b",
                "Beta Token",
                "2025-01-01",
            ),
        )
        conn.commit()

        assert m.get_coin_id("TEST") == "token-a"
        assert m.get_coin_id_with_name_hint("TEST", "Beta Token") == "token-b"
        assert m.get_coin_id_with_name_hint("TEST", "Alpha Token") == "token-a"
        assert m.get_coin_id_with_name_hint("TEST", None) == "token-a"
        assert m.get_coin_id_with_name_hint("TEST", "") == "token-a"
        m.close()


def test_attach_coin_gecko_ids_uses_name_hint_for_cmc_provider() -> None:
    from scanner.listings_and_volumes import attach_coin_gecko_ids_and_learn

    class FakeMapper:
        def get_coin_id_with_name_hint(self, symbol: str, name):
            if symbol == "ABC" and name == "Alpha Coin":
                return "alpha-gecko"
            return None

        def get_coin_id(self, symbol: str):
            return None

    calls = []

    class FakeResolver:
        def learn_from_cmc_listing_coin(self, **kwargs):
            calls.append(kwargs)

        def save_learned_if_dirty(self):
            pass

    coins = [
        {
            "symbol": "ABC",
            "name": "Alpha Coin",
            "slug": "different-from-gecko",
            "cmc_slug": "alpha-coin",
            "cmc_id": 1,
        }
    ]
    with_out, without = attach_coin_gecko_ids_and_learn(
        coins,
        top_coins_provider="cmc",
        cg_mapper=FakeMapper(),
        cmc_slug_resolver=FakeResolver(),
        app_logger=type("L", (), {"info": staticmethod(lambda *a, **k: None)})(),
    )
    assert without == []
    assert len(with_out) == 1
    assert with_out[0]["cg_id"] == "alpha-gecko"
    assert with_out[0]["gecko_id"] == "alpha-gecko"
