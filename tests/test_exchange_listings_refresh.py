"""Regression: exchange listing refresh must not wipe a populated DB on API failure."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from exchange_data.exchange_db import ExchangeDatabase
from exchange_data.exchange_fetcher import ExchangeFetcher


def _backdate_needs_update(db_path: Path, exchange: str) -> None:
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    old = (datetime.now() - timedelta(days=8)).isoformat()
    conn.execute(
        "UPDATE exchange_metadata SET last_updated=? WHERE exchange=?",
        (old, exchange),
    )
    conn.commit()
    conn.close()


def test_api_failure_preserves_populated_listings(tmp_path: Path) -> None:
    db_path = tmp_path / "exchanges.db"
    db = ExchangeDatabase(db_path)
    seed = [{"symbol": f"COIN{i}", "name": f"COIN{i}"} for i in range(200)]
    seed.append({"symbol": "RARETOKEN", "name": "Rare"})
    db.update_listings("mexc", seed, source="api")
    _backdate_needs_update(db_path, "mexc")

    fetcher = ExchangeFetcher(db)
    with patch.object(fetcher, "fetch_mexc_listings", return_value=[]):
        fetcher.update_all_exchanges(["mexc"])

    assert db.count_listings("mexc") == 201
    assert db.batch_check_listings(["RARETOKEN", "COIN0"], "mexc") == {
        "RARETOKEN": True,
        "COIN0": True,
    }
    # Refresh still due — do not stamp last_updated on failed fetch
    assert db.needs_update("mexc") is True


def test_empty_db_bootstrap_uses_fallback(tmp_path: Path) -> None:
    db_path = tmp_path / "exchanges.db"
    db = ExchangeDatabase(db_path)
    fetcher = ExchangeFetcher(db)

    with patch.object(fetcher, "fetch_kraken_listings", return_value=[]):
        fetcher.update_all_exchanges(["kraken"])

    assert db.count_listings("kraken") == len(fetcher._get_kraken_fallback())
    stats = db.get_exchange_stats()["kraken"]
    assert stats["source"] == "fallback"
    assert db.needs_update("kraken") is False


def test_coinbase_skips_delisted_products() -> None:
    fetcher = ExchangeFetcher(MagicMock())
    products = [
        {"base_currency": "BTC", "status": "online", "trading_disabled": False},
        {"base_currency": "EOS", "status": "delisted", "trading_disabled": False},
        {"base_currency": "GALA", "status": "online", "trading_disabled": True},
        {"base_currency": "ETH", "status": "online", "trading_disabled": False},
    ]
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = products
    with patch.object(fetcher.session, "get", return_value=resp):
        listings = fetcher.fetch_coinbase_listings()

    symbols = {row["symbol"] for row in listings}
    assert symbols == {"BTC", "ETH"}
