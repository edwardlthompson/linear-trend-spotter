"""Regression tests for scanner zero-result finalization paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import main
from database.models import ActiveCoinsDatabase
from scanner.top_coins_stage import TopCoinsDataset


class _Closeable:
    def close(self) -> None:
        pass


class _FakeExchangeDb(_Closeable):
    def batch_check_listings(self, symbols: list[str], exchange: str) -> dict[str, bool]:
        return {str(symbol).upper(): True for symbol in symbols}


class _MissingCgMapper(_Closeable):
    def get_coin_id_with_name_hint(self, symbol: str, name_hint: str | None = None) -> None:
        return None


def _provider_dataset(*, gains_7d: float, gains_30d: float, volume_24h: float = 10_000_000.0) -> TopCoinsDataset:
    row = {
        "data": {"id": 123, "symbol": "ABC", "slug": "alpha-beta"},
        "gains": {"7d": gains_7d, "30d": gains_30d},
        "info": {
            "symbol": "ABC",
            "name": "Alpha Beta",
            "slug": "alpha-beta",
            "volume_24h": volume_24h,
            "price": 1.23,
            "cmc_url": "https://coinmarketcap.com/currencies/alpha-beta/",
        },
    }
    return TopCoinsDataset(
        all_cmc_coins=[row],
        cmc_by_symbol={"ABC": row},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )


def _seed_active(active_db: ActiveCoinsDatabase) -> None:
    active_db.add_coin(
        {
            "symbol": "ABC",
            "name": "Alpha Beta",
            "slug": "alpha-beta",
            "gains": {"7d": 12.0, "30d": 45.0},
            "uniformity_score": 80.0,
            "exchange_volumes": {"coinbase": "$1,000,000"},
            "current_price": 1.23,
        }
    )


def _configure_scanner_test(monkeypatch: Any, tmp_path: Path, active_db: ActiveCoinsDatabase) -> None:
    config = dict(main.settings._config)
    config.update(
        {
            "ALERT_COOLDOWN_HOURS": 0,
            "ARTIFACT_HYGIENE_ENABLED": False,
            "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED": True,
            "PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET": "minimal",
            "SCAN_COSTS_ENABLED": False,
            "SCAN_HEARTBEAT_ENABLED": False,
            "MIN_VOLUME_M": 100,
            "TOP_COINS_PROVIDER": "cmc",
        }
    )
    monkeypatch.setattr(main.settings, "_config", config)
    monkeypatch.setattr(main.settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "fetch_vendor_quotas", lambda **kwargs: {})
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *args, **kwargs: (["ABC"], {"ABC"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **kwargs: None)
    monkeypatch.setattr(
        main,
        "initialize_runtime_components",
        lambda settings: {
            "history_db": _Closeable(),
            "active_db": active_db,
            "cache": _Closeable(),
            "exchange_db": _FakeExchangeDb(),
            "tv_mapper": _Closeable(),
            "cmc": object(),
            "gecko": object(),
            "history_fallback": object(),
            "cg_mapper": _MissingCgMapper(),
            "cmc_slug_resolver": None,
        },
    )


def _snapshot_payload(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "qualified_public_snapshot.json").read_text(encoding="utf-8"))


def test_no_gain_qualified_clears_snapshot_and_active_exits(monkeypatch, tmp_path) -> None:
    active_db = ActiveCoinsDatabase(tmp_path / "scanner.db")
    _seed_active(active_db)
    _configure_scanner_test(monkeypatch, tmp_path, active_db)
    monkeypatch.setattr(
        main,
        "fetch_top_coins_dataset",
        lambda **kwargs: _provider_dataset(gains_7d=1.0, gains_30d=2.0),
    )

    main.run_scanner()

    payload = _snapshot_payload(tmp_path)
    assert payload["coins"] == []
    assert payload["coins_evaluated"] == 1
    assert payload["qualification_exits"] == [
        {"symbol": "ABC", "exit_reason": "7d gain below threshold (1.0% < 7%)"}
    ]
    assert active_db.get_active() == {}


def test_no_coingecko_ids_clears_snapshot_and_active_exits(monkeypatch, tmp_path) -> None:
    active_db = ActiveCoinsDatabase(tmp_path / "scanner.db")
    _seed_active(active_db)
    _configure_scanner_test(monkeypatch, tmp_path, active_db)
    monkeypatch.setattr(
        main,
        "fetch_top_coins_dataset",
        lambda **kwargs: _provider_dataset(gains_7d=12.0, gains_30d=45.0),
    )

    main.run_scanner()

    payload = _snapshot_payload(tmp_path)
    assert payload["coins"] == []
    assert payload["coins_evaluated"] == 1
    assert payload["qualification_exits"] == [
        {"symbol": "ABC", "exit_reason": "No CoinGecko ID mapping"}
    ]
    assert active_db.get_active() == {}
