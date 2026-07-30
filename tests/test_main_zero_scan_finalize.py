from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import main


class _Closable:
    def close(self) -> None:
        pass


class _ActiveDB:
    def __init__(self) -> None:
        self.exited = [{"symbol": "AAA"}]
        self.calls: list[tuple[list[dict], int]] = []

    def get_entered_exited(self, current_coins, cooldown_hours: int = 0):
        self.calls.append((list(current_coins), cooldown_hours))
        return [], self.exited, []


def _install_common_scan_mocks(monkeypatch, tmp_path, *, gain_qualified, cg_result):
    active_db = _ActiveDB()
    runtime = {
        "history_db": object(),
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
    top_dataset = SimpleNamespace(
        all_cmc_coins=[],
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )

    monkeypatch.setattr(main.settings, "DATA_DIR", tmp_path)
    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setattr(main, "initialize_runtime_components", lambda settings: runtime)
    monkeypatch.setattr(main, "fetch_top_coins_dataset", lambda **kwargs: top_dataset)
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *args, **kwargs: (["AAA"], {"AAA"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **kwargs: None)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: gain_qualified)
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *args, **kwargs: cg_result)
    monkeypatch.setattr(main, "fetch_vendor_quotas", lambda **kwargs: {})
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", MagicMock())
    write_snapshot = MagicMock()
    web_notify = MagicMock()
    ntfy_notify = MagicMock()
    monkeypatch.setattr(main, "write_public_qualified_snapshot", write_snapshot)
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", web_notify)
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", ntfy_notify)

    def _tag_exit_reasons(exited, **kwargs):
        for coin in exited:
            coin["exit_reason"] = "No longer met qualification criteria"

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", _tag_exit_reasons)
    return active_db, write_snapshot, web_notify, ntfy_notify


def test_zero_gain_scan_finalizes_exits_and_publishes_empty_snapshot(monkeypatch, tmp_path) -> None:
    active_db, write_snapshot, web_notify, ntfy_notify = _install_common_scan_mocks(
        monkeypatch,
        tmp_path,
        gain_qualified=[],
        cg_result=([], []),
    )

    main.run_scanner()

    assert active_db.calls == [([], main.settings.alert_cooldown_hours)]
    assert write_snapshot.call_args.args[2] == []
    assert write_snapshot.call_args.kwargs["qualification_exits"] == active_db.exited
    web_notify.assert_called_once_with([], active_db.exited)
    ntfy_notify.assert_called_once_with([], active_db.exited)


def test_zero_cg_id_scan_finalizes_exits_and_publishes_empty_snapshot(monkeypatch, tmp_path) -> None:
    active_db, write_snapshot, web_notify, ntfy_notify = _install_common_scan_mocks(
        monkeypatch,
        tmp_path,
        gain_qualified=[{"symbol": "AAA"}],
        cg_result=([], ["AAA"]),
    )

    main.run_scanner()

    assert active_db.calls == [([], main.settings.alert_cooldown_hours)]
    assert write_snapshot.call_args.args[2] == []
    assert write_snapshot.call_args.kwargs["qualification_exits"] == active_db.exited
    web_notify.assert_called_once_with([], active_db.exited)
    ntfy_notify.assert_called_once_with([], active_db.exited)
