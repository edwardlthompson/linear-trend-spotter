"""Regression coverage for healthy zero-result scanner runs."""

from __future__ import annotations

from types import SimpleNamespace

import main


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ActiveDb:
    def __init__(self) -> None:
        self.current_coins = None
        self.cooldown_hours = None

    def get_entered_exited(self, current_coins, cooldown_hours=0):
        self.current_coins = current_coins
        self.cooldown_hours = cooldown_hours
        return [], [{"symbol": "OLD", "name": "Old Coin"}], []


def _install_common_zero_scan_fakes(monkeypatch, tmp_path, *, active_db: _ActiveDb):
    cache = _Closable()
    exchange_db = _Closable()
    tv_mapper = _Closable()
    cg_mapper = _Closable()
    runtime = {
        "history_db": object(),
        "active_db": active_db,
        "cache": cache,
        "exchange_db": exchange_db,
        "tv_mapper": tv_mapper,
        "cmc": object(),
        "gecko": object(),
        "history_fallback": object(),
        "cg_mapper": cg_mapper,
        "cmc_slug_resolver": object(),
    }
    top_dataset = SimpleNamespace(
        all_cmc_coins=[],
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )
    writes = []
    web_notifications = []
    ntfy_notifications = []
    attach_calls = []

    monkeypatch.setattr(main.settings, "DATA_DIR", tmp_path)
    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FILE", "snapshot.json")
    monkeypatch.setattr(main, "initialize_runtime_components", lambda settings: runtime)
    monkeypatch.setattr(main, "fetch_top_coins_dataset", lambda **kwargs: top_dataset)
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *args, **kwargs: (["OLD"], {"OLD"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **kwargs: None)
    monkeypatch.setattr(main, "update_exit_reason_analytics", lambda *args, **kwargs: {})
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", lambda entered, exited: web_notifications.append((entered, exited)))
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", lambda entered, exited: ntfy_notifications.append((entered, exited)))

    def fake_attach_exit_reasons(exited, **kwargs):
        attach_calls.append(kwargs)
        for coin in exited:
            coin["exit_reason"] = "No longer qualified"

    def fake_write_snapshot(data_dir, filename, coins, **kwargs):
        writes.append(
            {
                "data_dir": data_dir,
                "filename": filename,
                "coins": coins,
                "kwargs": kwargs,
            }
        )

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", fake_attach_exit_reasons)
    monkeypatch.setattr(main, "write_public_qualified_snapshot", fake_write_snapshot)
    return {
        "cache": cache,
        "exchange_db": exchange_db,
        "tv_mapper": tv_mapper,
        "cg_mapper": cg_mapper,
        "writes": writes,
        "web_notifications": web_notifications,
        "ntfy_notifications": ntfy_notifications,
        "attach_calls": attach_calls,
    }


def test_no_gain_qualified_finalizes_exits_and_publishes_empty_snapshot(monkeypatch, tmp_path) -> None:
    active_db = _ActiveDb()
    state = _install_common_zero_scan_fakes(monkeypatch, tmp_path, active_db=active_db)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: [])

    main.run_scanner()

    assert active_db.current_coins == []
    assert state["attach_calls"][0]["gain_qualified_symbols"] == set()
    assert state["attach_calls"][0]["coins_with_cg_ids_symbols"] == set()
    assert state["writes"][0]["coins"] == []
    assert state["writes"][0]["kwargs"]["qualification_exits"][0]["symbol"] == "OLD"
    assert state["web_notifications"][0][1][0]["symbol"] == "OLD"
    assert state["ntfy_notifications"][0][1][0]["symbol"] == "OLD"
    assert state["cache"].closed
    assert state["exchange_db"].closed
    assert state["tv_mapper"].closed
    assert state["cg_mapper"].closed


def test_no_coingecko_ids_finalizes_exits_after_gain_filter(monkeypatch, tmp_path) -> None:
    active_db = _ActiveDb()
    state = _install_common_zero_scan_fakes(monkeypatch, tmp_path, active_db=active_db)
    gain_coin = {"symbol": "OLD", "name": "Old Coin"}
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: [gain_coin])
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *args, **kwargs: ([], [gain_coin]))

    main.run_scanner()

    assert active_db.current_coins == []
    assert state["attach_calls"][0]["gain_qualified_symbols"] == {"OLD"}
    assert state["attach_calls"][0]["coins_with_cg_ids_symbols"] == set()
    assert state["writes"][0]["coins"] == []
    assert state["writes"][0]["kwargs"]["qualification_exits"][0]["symbol"] == "OLD"
