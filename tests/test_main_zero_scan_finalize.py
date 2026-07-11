"""Regression coverage for healthy scans that produce zero qualified coins."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import main


class _Closable:
    def close(self) -> None:
        pass


class _ActiveDb:
    def __init__(self) -> None:
        self.exited = [{"symbol": "BTC"}]
        self.calls: list[tuple[list[dict], int]] = []

    def get_entered_exited(self, current_coins: list[dict], cooldown_hours: int = 0) -> tuple:
        self.calls.append((current_coins, cooldown_hours))
        return [], self.exited, []


def _install_common_scan_mocks(monkeypatch, active_db: _ActiveDb) -> None:
    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "ALERT_COOLDOWN_HOURS", 6)
    monkeypatch.setattr(
        main,
        "initialize_runtime_components",
        lambda _settings: {
            "history_db": SimpleNamespace(),
            "active_db": active_db,
            "cache": _Closable(),
            "exchange_db": _Closable(),
            "tv_mapper": _Closable(),
            "cmc": object(),
            "gecko": object(),
            "history_fallback": object(),
            "cg_mapper": _Closable(),
            "cmc_slug_resolver": object(),
        },
    )
    monkeypatch.setattr(
        main,
        "fetch_top_coins_dataset",
        lambda **_kwargs: SimpleNamespace(
            all_cmc_coins=[],
            cmc_by_symbol={"BTC": {"gains": {"7d": 0.0, "30d": 0.0}, "info": {"volume_24h": 1}}},
            cmc_by_normalized_symbol={},
            cmc_symbol_aliases={},
            coingecko_id_aliases={},
        ),
    )
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *_args, **_kwargs: (["BTC"], {"BTC"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **_kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **_kwargs: None)
    monkeypatch.setattr(main, "update_exit_reason_analytics", lambda *_args, **_kwargs: {"last_run": {"exits": 1}})
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", Mock())
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", Mock())
    monkeypatch.setattr(main, "_publish_public_snapshot", Mock())

    def mark_reasons(exited: list[dict], **_kwargs) -> None:
        for coin in exited:
            coin["exit_reason"] = "regression-test"

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", Mock(side_effect=mark_reasons))


def test_no_gain_qualified_scan_finalizes_exits_and_publishes_empty_snapshot(monkeypatch) -> None:
    active_db = _ActiveDb()
    _install_common_scan_mocks(monkeypatch, active_db)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *_args, **_kwargs: [])

    main.run_scanner()

    assert active_db.calls == [([], 6)]
    main.attach_exit_reasons_and_register.assert_called_once()
    assert main.attach_exit_reasons_and_register.call_args.kwargs["all_symbols_set"] == {"BTC"}
    assert main.attach_exit_reasons_and_register.call_args.kwargs["gain_qualified_symbols"] == set()
    main._publish_public_snapshot.assert_called_once()
    assert main._publish_public_snapshot.call_args.kwargs["final_results"] == []
    assert main._publish_public_snapshot.call_args.kwargs["exited"] == active_db.exited
    main.maybe_notify_web_push_qualified_changes.assert_called_once_with([], active_db.exited)
    main.maybe_notify_ntfy_qualified_changes.assert_called_once_with([], active_db.exited)


def test_no_coingecko_ids_scan_still_finalizes_exits(monkeypatch) -> None:
    active_db = _ActiveDb()
    _install_common_scan_mocks(monkeypatch, active_db)
    gain_coin = {"symbol": "BTC", "name": "Bitcoin", "gains": {"7d": 10.0, "30d": 40.0}}
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *_args, **_kwargs: [gain_coin])
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *_args, **_kwargs: ([], [gain_coin]))

    main.run_scanner()

    assert active_db.calls == [([], 6)]
    main.attach_exit_reasons_and_register.assert_called_once()
    assert main.attach_exit_reasons_and_register.call_args.kwargs["gain_qualified_symbols"] == {"BTC"}
    assert main.attach_exit_reasons_and_register.call_args.kwargs["coins_with_cg_ids_symbols"] == set()
    main._publish_public_snapshot.assert_called_once()
