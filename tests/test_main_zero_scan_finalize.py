"""Regression coverage for healthy zero-result scanner finalization."""

from __future__ import annotations

from types import SimpleNamespace

import main


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ActiveDB:
    def __init__(self) -> None:
        self.current_rows = None
        self.registered: list[tuple[str, str, int]] = []

    def get_entered_exited(self, current_rows, cooldown_hours: int = 0):
        self.current_rows = list(current_rows)
        return [], [{"symbol": "OLD", "name": "Old", "slug": "old"}], []

    def register_exit(self, symbol: str, reason: str = "", cooldown_hours: int = 0) -> None:
        self.registered.append((symbol, reason, cooldown_hours))


def test_no_gain_scan_publishes_empty_snapshot_and_exit_notifications(monkeypatch):
    active_db = _ActiveDB()
    tv_mapper = _Closable()
    exchange_db = _Closable()
    cg_mapper = _Closable()
    cache = _Closable()
    runtime = {
        "history_db": SimpleNamespace(),
        "active_db": active_db,
        "cache": cache,
        "exchange_db": exchange_db,
        "tv_mapper": tv_mapper,
        "cmc": SimpleNamespace(),
        "gecko": SimpleNamespace(),
        "history_fallback": SimpleNamespace(),
        "cg_mapper": cg_mapper,
        "cmc_slug_resolver": SimpleNamespace(),
    }
    top_dataset = SimpleNamespace(
        all_cmc_coins=[],
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )

    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setattr(main, "initialize_runtime_components", lambda _settings: runtime)
    monkeypatch.setattr(main, "fetch_top_coins_dataset", lambda **_kwargs: top_dataset)
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *_args, **_kwargs: (["OLD"], {"OLD"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **_kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **_kwargs: None)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "fetch_vendor_quotas", lambda **_kwargs: {})
    monkeypatch.setattr(main, "build_api_cost_panel_for_snapshot", lambda *_args, **_kwargs: {})

    def fake_exit_reasons(exited, *, active_db, settings, **_kwargs):
        for coin in exited:
            coin["exit_reason"] = "Failed gain/volume filter"
            active_db.register_exit(
                coin["symbol"],
                reason=coin["exit_reason"],
                cooldown_hours=settings.alert_cooldown_hours,
            )

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", fake_exit_reasons)

    writes = []
    monkeypatch.setattr(
        main,
        "write_public_qualified_snapshot",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )
    pushed = []
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *args: pushed.append(args))
    web_notifies = []
    ntfy_notifies = []
    monkeypatch.setattr(
        main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: web_notifies.append((entered, exited)),
    )
    monkeypatch.setattr(
        main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: ntfy_notifies.append((entered, exited)),
    )

    main.run_scanner()

    assert active_db.current_rows == []
    assert active_db.registered == [("OLD", "Failed gain/volume filter", main.settings.alert_cooldown_hours)]
    assert writes
    args, kwargs = writes[0]
    assert args[2] == []
    assert kwargs["qualification_exits"][0]["symbol"] == "OLD"
    assert kwargs["qualification_exits"][0]["exit_reason"] == "Failed gain/volume filter"
    assert pushed
    assert web_notifies == [([], kwargs["qualification_exits"])]
    assert ntfy_notifies == [([], kwargs["qualification_exits"])]
    assert tv_mapper.closed
    assert exchange_db.closed
    assert cg_mapper.closed
    assert cache.closed
