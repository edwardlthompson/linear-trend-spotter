"""Regression: target venues with empty listings must refresh even when union is non-empty."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from exchange_data.exchange_db import ExchangeDatabase
from scanner.exchange_universe import load_exchange_symbol_universe


class ExchangeUniverseRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "exchanges.db"
        self.db = ExchangeDatabase(self.db_path)

    def tearDown(self) -> None:
        self.db.close()
        self._tmpdir.cleanup()

    def test_adds_missing_target_exchange_listings(self) -> None:
        self.db.update_listings(
            "coinbase",
            [{"symbol": "BTC", "name": "Bitcoin"}, {"symbol": "ETH", "name": "Ethereum"}],
            source="api",
        )
        calls: list[list[str]] = []

        class FakeFetcher:
            def __init__(self, exchange_db: ExchangeDatabase) -> None:
                self.db = exchange_db

            def update_all_exchanges(self, target_exchanges: list[str] | None = None) -> None:
                calls.append(list(target_exchanges or []))
                self.db.update_listings(
                    "kraken",
                    [
                        {"symbol": "BTC", "name": "Bitcoin"},
                        {"symbol": "KONLY", "name": "Kraken Only"},
                    ],
                    source="api",
                )

        logger = MagicMock()
        symbols, symbol_set = load_exchange_symbol_universe(
            self.db_path,
            self.db,
            FakeFetcher,
            logger,
            target_exchanges=("coinbase", "kraken"),
        )

        self.assertEqual(calls, [["coinbase", "kraken"]])
        self.assertIn("KONLY", symbol_set)
        self.assertIn("BTC", symbol_set)
        self.assertGreaterEqual(len(symbols), 3)

        with sqlite3.connect(self.db_path) as conn:
            kraken_count = conn.execute(
                "SELECT COUNT(*) FROM exchange_listings WHERE exchange = ?",
                ("kraken",),
            ).fetchone()[0]
        self.assertEqual(kraken_count, 2)

    def test_skips_refresh_when_all_targets_have_listings(self) -> None:
        self.db.update_listings(
            "coinbase",
            [{"symbol": "BTC", "name": "Bitcoin"}],
            source="api",
        )
        self.db.update_listings(
            "kraken",
            [{"symbol": "ETH", "name": "Ethereum"}],
            source="api",
        )
        calls: list[list[str]] = []

        class FakeFetcher:
            def __init__(self, exchange_db: ExchangeDatabase) -> None:
                self.db = exchange_db

            def update_all_exchanges(self, target_exchanges: list[str] | None = None) -> None:
                calls.append(list(target_exchanges or []))

        logger = MagicMock()
        symbols, symbol_set = load_exchange_symbol_universe(
            self.db_path,
            self.db,
            FakeFetcher,
            logger,
            target_exchanges=("coinbase", "kraken"),
        )

        self.assertEqual(calls, [])
        self.assertEqual(symbol_set, {"BTC", "ETH"})
        self.assertEqual(set(symbols), {"BTC", "ETH"})

    def test_needs_update_true_when_metadata_exists_but_listings_empty(self) -> None:
        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO exchange_metadata (exchange, last_updated, total_pairs, source)
                VALUES (?, datetime('now'), ?, ?)
                """,
                ("mexc", 0, "stale"),
            )
            conn.commit()

        self.assertTrue(self.db.needs_update("mexc"))
        self.assertTrue(self.db.needs_update("kraken"))  # no metadata
        self.db.update_listings(
            "coinbase",
            [{"symbol": "BTC", "name": "Bitcoin"}],
            source="api",
        )
        self.assertFalse(self.db.needs_update("coinbase"))


if __name__ == "__main__":
    unittest.main()
