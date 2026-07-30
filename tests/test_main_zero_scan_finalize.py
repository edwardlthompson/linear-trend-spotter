"""Regression tests for healthy zero-result scanner finalization."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import main


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ActiveDb:
    def __init__(self) -> None:
        self.current_sets: list[list[dict[str, Any]]] = []
        self.exited = [{"symbol": "OLD", "listed_on": ["kraken"]}]

    def get_entered_exited(
        self,
        current_coins: list[dict[str, Any]],
        cooldown_hours: int = 0,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        self.current_sets.append(current_coins)
        return [], self.exited, []


def _install_zero_scan_runtime(monkeypatch) -> tuple[_ActiveDb, dict[str, _Closable]]:
    active_db = _ActiveDb()
    closables = {
        "cache": _Closable(),
        "exchange_db": _Closable(),
        "tv_mapper": _Closable(),
        "cg_mapper": _Closable(),
    }
    runtime = {
        "history_db": object(),
        "active_db": active_db,
        "cmc": object(),
        "gecko": object(),
        "history_fallback": object(),
        "cmc_slug_resolver": object(),
        **closables,
    }
    monkeypatch.setattr(main, "initialize_runtime_components", lambda settings: runtime)
    monkeypatch.setattr(
        main,
        "fetch_top_coins_dataset",
        lambda **kwargs: SimpleNamespace(
            all_cmc_coins=[],
            cmc_by_symbol={},
            cmc_by_normalized_symbol={},
            cmc_symbol_aliases={},
            coingecko_id_aliases={},
        ),
    )
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *args, **kwargs: (["OLD"], {"OLD"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **kwargs: None)
    monkeypatch.setattr(main, "run_artifact_hygiene", lambda *args, **kwargs: {})
    monkeypatch.setattr(main.metrics, "save", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "update_exit_reason_analytics", lambda *args, **kwargs: {})
    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "SCAN_HEARTBEAT_ENABLED", False)
    return active_db, closables


def test_no_gain_qualified_scan_publishes_exits(monkeypatch) -> None:
    active_db, closables = _install_zero_scan_runtime(monkeypatch)
    publish_calls: list[dict[str, Any]] = []
    push_calls: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []
    attach_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        main,
        "attach_exit_reasons_and_register",
        lambda exited, **kwargs: attach_calls.append({"exited": exited, **kwargs}),
    )
    monkeypatch.setattr(
        main,
        "_publish_public_snapshot",
        lambda final_results, **kwargs: publish_calls.append({"final_results": final_results, **kwargs}),
    )
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", lambda entered, exited: push_calls.append((entered, exited)))
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", lambda entered, exited: None)

    main.run_scanner()

    assert active_db.current_sets == [[]]
    assert attach_calls[0]["exited"] == active_db.exited
    assert attach_calls[0]["gain_qualified_symbols"] == set()
    assert publish_calls[0]["final_results"] == []
    assert publish_calls[0]["exited"] == active_db.exited
    assert push_calls == [([], active_db.exited)]
    assert all(c.closed for c in closables.values())


def test_no_coingecko_ids_scan_publishes_exits_with_gain_context(monkeypatch) -> None:
    active_db, _closables = _install_zero_scan_runtime(monkeypatch)
    gain_rows = [{"symbol": "OLD", "name": "Old Coin", "gains": {"7d": 8.0, "30d": 40.0}}]
    attach_calls: list[dict[str, Any]] = []
    publish_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: gain_rows)
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *args, **kwargs: ([], gain_rows))
    monkeypatch.setattr(
        main,
        "attach_exit_reasons_and_register",
        lambda exited, **kwargs: attach_calls.append({"exited": exited, **kwargs}),
    )
    monkeypatch.setattr(
        main,
        "_publish_public_snapshot",
        lambda final_results, **kwargs: publish_calls.append({"final_results": final_results, **kwargs}),
    )
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", lambda entered, exited: None)
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", lambda entered, exited: None)

    main.run_scanner()

    assert active_db.current_sets == [[]]
    assert attach_calls[0]["gain_qualified_symbols"] == {"OLD"}
    assert attach_calls[0]["coins_with_cg_ids_symbols"] == set()
    assert publish_calls[0]["final_results"] == []
    assert publish_calls[0]["exited"] == active_db.exited
