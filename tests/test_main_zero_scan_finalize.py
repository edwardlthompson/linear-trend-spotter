"""Regression tests for healthy zero-result scanner finalization."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import main


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ActiveDb:
    def __init__(self) -> None:
        self.current = None
        self.exited = [{"symbol": "OLD", "name": "Oldcoin", "slug": "oldcoin"}]
        self.registered = []

    def get_entered_exited(self, current, cooldown_hours=0):
        self.current = current
        return [], self.exited, []

    def register_exit(self, symbol, reason="", cooldown_hours=0):
        self.registered.append((symbol, reason, cooldown_hours))


def _top_dataset() -> SimpleNamespace:
    return SimpleNamespace(
        all_cmc_coins=[],
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )


def _install_common_scan_fakes(monkeypatch, active_db: _ActiveDb) -> dict[str, _Closable]:
    resources = {
        "history_db": _Closable(),
        "active_db": active_db,
        "cache": _Closable(),
        "exchange_db": _Closable(),
        "tv_mapper": _Closable(),
        "cmc": object(),
        "gecko": object(),
        "history_fallback": object(),
        "cg_mapper": _Closable(),
        "cmc_slug_resolver": object(),
    }
    monkeypatch.setattr(main, "initialize_runtime_components", lambda _settings: resources)
    monkeypatch.setattr(main, "fetch_top_coins_dataset", lambda **_kwargs: _top_dataset())
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *_args, **_kwargs: (["OLD"], {"OLD"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **_kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **_kwargs: None)
    monkeypatch.setattr(main, "fetch_vendor_quotas", lambda **_kwargs: {})
    monkeypatch.setattr(main.metrics, "save", lambda *_args, **_kwargs: None)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(main.settings._config, "SCAN_HEARTBEAT_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "NTFY_ENABLED", False)
    return resources


def test_no_gain_qualified_scan_publishes_exits(monkeypatch) -> None:
    active_db = _ActiveDb()
    resources = _install_common_scan_fakes(monkeypatch, active_db)
    attach_exit = MagicMock(side_effect=lambda exited, **_kwargs: exited[0].update({"exit_reason": "Failed gain"}))
    write_snapshot = MagicMock()
    web_notify = MagicMock()
    ntfy_notify = MagicMock()
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "attach_exit_reasons_and_register", attach_exit)
    monkeypatch.setattr(main, "write_public_qualified_snapshot", write_snapshot)
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", MagicMock())
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", web_notify)
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", ntfy_notify)

    main.run_scanner()

    assert active_db.current == []
    assert resources["cache"].closed is True
    assert attach_exit.call_args.kwargs["gain_qualified_symbols"] == set()
    assert write_snapshot.call_args.args[2] == []
    assert write_snapshot.call_args.kwargs["qualification_exits"] == active_db.exited
    web_notify.assert_called_once_with([], active_db.exited)
    ntfy_notify.assert_called_once_with([], active_db.exited)


def test_no_coingecko_ids_scan_publishes_exits_with_gain_context(monkeypatch) -> None:
    active_db = _ActiveDb()
    _install_common_scan_fakes(monkeypatch, active_db)
    gain_rows = [{"symbol": "OLD", "name": "Oldcoin", "gains": {"7d": 10, "30d": 40}}]
    attach_exit = MagicMock(side_effect=lambda exited, **_kwargs: exited[0].update({"exit_reason": "No CG ID"}))
    write_snapshot = MagicMock()
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *_args, **_kwargs: gain_rows)
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *_args, **_kwargs: ([], gain_rows))
    monkeypatch.setattr(main, "attach_exit_reasons_and_register", attach_exit)
    monkeypatch.setattr(main, "write_public_qualified_snapshot", write_snapshot)
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", MagicMock())
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", MagicMock())
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", MagicMock())

    main.run_scanner()

    assert active_db.current == []
    assert attach_exit.call_args.kwargs["gain_qualified_symbols"] == {"OLD"}
    assert attach_exit.call_args.kwargs["coins_with_cg_ids_symbols"] == set()
    assert write_snapshot.call_args.args[2] == []
    assert write_snapshot.call_args.kwargs["qualification_exits"] == active_db.exited
