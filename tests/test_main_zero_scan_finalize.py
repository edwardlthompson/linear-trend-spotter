"""Regression coverage for healthy zero-result scans."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _runtime() -> dict[str, object]:
    return {
        "history_db": object(),
        "active_db": object(),
        "cache": _Closable(),
        "exchange_db": _Closable(),
        "tv_mapper": _Closable(),
        "cmc": object(),
        "gecko": object(),
        "history_fallback": object(),
        "cg_mapper": _Closable(),
        "cmc_slug_resolver": object(),
    }


def _top_dataset() -> SimpleNamespace:
    return SimpleNamespace(
        all_cmc_coins=[],
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )


def _patch_common_scan_setup(monkeypatch, main_module, runtime):
    monkeypatch.setattr(main_module, "initialize_runtime_components", lambda settings: runtime)
    monkeypatch.setattr(main_module, "fetch_top_coins_dataset", lambda **kwargs: _top_dataset())
    monkeypatch.setattr(
        main_module,
        "load_exchange_symbol_universe",
        lambda *args, **kwargs: (["ABC"], {"ABC"}),
    )
    monkeypatch.setattr(main_module, "prefetch_alias_markets_by_gecko_id", lambda **kwargs: {})
    monkeypatch.setattr(main_module, "top_up_alias_markets_for_symbols", lambda **kwargs: None)
    monkeypatch.setattr(main_module.metrics, "reset", lambda: None)


def test_run_scanner_finalizes_when_gain_filter_has_zero_results(monkeypatch):
    import main

    runtime = _runtime()
    _patch_common_scan_setup(monkeypatch, main, runtime)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: [])

    calls = []

    def fake_finalize(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(main, "_finalize_zero_qualified_scan", fake_finalize)

    main.run_scanner()

    assert len(calls) == 1
    assert calls[0]["gain_qualified_symbols"] == set()
    assert calls[0]["coins_with_cg_ids_symbols"] == set()
    assert calls[0]["all_symbols_set"] == {"ABC"}
    assert runtime["cache"].closed is True


def test_run_scanner_finalizes_when_no_coingecko_ids(monkeypatch):
    import main

    runtime = _runtime()
    _patch_common_scan_setup(monkeypatch, main, runtime)
    coin = {"symbol": "ABC", "name": "ABC", "gains": {"7d": 10, "30d": 40}}
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: [coin])
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *args, **kwargs: ([], [coin]))

    calls = []

    def fake_finalize(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(main, "_finalize_zero_qualified_scan", fake_finalize)

    main.run_scanner()

    assert len(calls) == 1
    assert calls[0]["gain_qualified_symbols"] == {"ABC"}
    assert calls[0]["coins_with_cg_ids_symbols"] == set()
    assert calls[0]["all_symbols_set"] == {"ABC"}
    assert runtime["cache"].closed is True


def test_zero_qualified_finalizer_clears_active_snapshot_and_notifies(tmp_path, monkeypatch):
    import main

    class Settings:
        alert_cooldown_hours = 6
        exit_analytics_file = tmp_path / "exit_analytics.json"
        scan_heartbeat_enabled = False
        public_qualified_snapshot_enabled = True
        DATA_DIR = tmp_path
        public_qualified_snapshot_file = "qualified_public_snapshot.json"
        public_qualified_snapshot_field_set = "full"
        scan_interval_seconds = 3600
        ntfy_enabled = True
        ntfy_base_url = "https://ntfy.example"
        ntfy_topic = "topic"

    class ActiveDb:
        def __init__(self) -> None:
            self.calls = []

        def get_entered_exited(self, current_coins, cooldown_hours=0):
            self.calls.append((current_coins, cooldown_hours))
            return [], [{"symbol": "ABC"}], []

    active_db = ActiveDb()
    attached = []
    snapshots = []
    relays = []
    web_notifications = []
    ntfy_notifications = []

    def fake_attach(exited, **kwargs):
        attached.append((list(exited), kwargs))
        exited[0]["exit_reason"] = "Failed gain/volume filter"

    def fake_snapshot(data_dir, filename, rows, **kwargs):
        snapshots.append((data_dir, filename, list(rows), kwargs))

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", fake_attach)
    monkeypatch.setattr(
        main,
        "update_exit_reason_analytics",
        lambda path, exited: {"last_run": {"exits": len(exited)}, "total_exits": len(exited)},
    )
    monkeypatch.setattr(main, "write_public_qualified_snapshot", fake_snapshot)
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *args: relays.append(args))
    monkeypatch.setattr(
        main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: web_notifications.append((entered, exited)),
    )
    monkeypatch.setattr(
        main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: ntfy_notifications.append((entered, exited)),
    )
    monkeypatch.setattr(main.metrics, "get_summary", lambda: {"errors": {"api": 2, "flag": True}})

    main._finalize_zero_qualified_scan(
        active_db=active_db,
        settings_obj=Settings(),
        all_symbols_set={"ABC"},
        top_coins_provider="cmc",
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gecko=object(),
        alias_markets_by_id={},
        gain_qualified_symbols=set(),
        coins_with_cg_ids_symbols=set(),
        scan_started_at=datetime.now(timezone.utc),
    )

    assert active_db.calls == [([], 6)]
    assert attached[0][0] == [{"symbol": "ABC", "exit_reason": "Failed gain/volume filter"}]
    assert attached[0][1]["gain_qualified_symbols"] == set()
    assert snapshots[0][2] == []
    assert snapshots[0][3]["qualification_exits"] == [
        {"symbol": "ABC", "exit_reason": "Failed gain/volume filter"}
    ]
    assert snapshots[0][3]["notify_public_config"] == {
        "ntfy_subscribe_url": "https://ntfy.example/topic"
    }
    assert snapshots[0][3]["scan_health"]["errors_count"] == 2
    assert relays == [(tmp_path, "qualified_public_snapshot.json")]
    assert web_notifications == [([], [{"symbol": "ABC", "exit_reason": "Failed gain/volume filter"}])]
    assert ntfy_notifications == [([], [{"symbol": "ABC", "exit_reason": "Failed gain/volume filter"}])]
