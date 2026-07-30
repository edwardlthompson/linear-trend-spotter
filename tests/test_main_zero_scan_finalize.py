"""Regression tests for healthy scans that produce zero qualified coins."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import main as scanner_main


def test_zero_gain_scan_finalizes_exits_snapshot_and_notifications(monkeypatch) -> None:
    monkeypatch.setitem(scanner_main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(scanner_main.settings._config, "SCAN_HEARTBEAT_ENABLED", False)

    active_db = MagicMock()
    exited = [{"symbol": "OLD", "name": "Old Coin", "slug": "old-coin"}]
    active_db.get_entered_exited.return_value = ([], exited, [])
    runtime = {
        "history_db": MagicMock(),
        "active_db": active_db,
        "cache": MagicMock(),
        "exchange_db": MagicMock(),
        "tv_mapper": MagicMock(),
        "cmc": MagicMock(),
        "gecko": MagicMock(),
        "history_fallback": MagicMock(),
        "cg_mapper": MagicMock(),
        "cmc_slug_resolver": None,
    }

    def attach_exit_reasons(exited_rows: list[dict], **kwargs: object) -> None:
        assert kwargs["gain_qualified_symbols"] == set()
        assert kwargs["coins_with_cg_ids_symbols"] == set()
        for row in exited_rows:
            row["exit_reason"] = "Failed gain/volume filter"

    monkeypatch.setattr(scanner_main, "initialize_runtime_components", lambda settings: runtime)
    monkeypatch.setattr(
        scanner_main,
        "fetch_top_coins_dataset",
        lambda **kwargs: SimpleNamespace(
            all_cmc_coins=[],
            cmc_by_symbol={},
            cmc_by_normalized_symbol={},
            cmc_symbol_aliases={},
            coingecko_id_aliases={},
        ),
    )
    monkeypatch.setattr(scanner_main, "load_exchange_symbol_universe", lambda *args, **kwargs: (["OLD"], {"OLD"}))
    monkeypatch.setattr(scanner_main, "prefetch_alias_markets_by_gecko_id", lambda **kwargs: {})
    monkeypatch.setattr(scanner_main, "top_up_alias_markets_for_symbols", lambda **kwargs: None)
    monkeypatch.setattr(scanner_main, "apply_gain_volume_filter", lambda *args, **kwargs: [])
    monkeypatch.setattr(scanner_main, "attach_exit_reasons_and_register", attach_exit_reasons)
    monkeypatch.setattr(
        scanner_main,
        "update_exit_reason_analytics",
        MagicMock(return_value={"last_run": {"exits": 1}, "total_exits": 1}),
    )
    write_snapshot = MagicMock()
    push_relay = MagicMock()
    notify_web = MagicMock()
    notify_ntfy = MagicMock()
    monkeypatch.setattr(scanner_main, "write_public_qualified_snapshot", write_snapshot)
    monkeypatch.setattr(scanner_main, "maybe_push_qualified_snapshot_relay", push_relay)
    monkeypatch.setattr(scanner_main, "maybe_notify_web_push_qualified_changes", notify_web)
    monkeypatch.setattr(scanner_main, "maybe_notify_ntfy_qualified_changes", notify_ntfy)

    scanner_main.run_scanner()

    active_db.get_entered_exited.assert_called_once_with(
        [],
        cooldown_hours=scanner_main.settings.alert_cooldown_hours,
    )
    write_snapshot.assert_called_once()
    assert write_snapshot.call_args.args[2] == []
    assert write_snapshot.call_args.kwargs["qualification_exits"] == exited
    push_relay.assert_called_once()
    notify_web.assert_called_once_with([], exited)
    notify_ntfy.assert_called_once_with([], exited)
    runtime["cache"].close.assert_called_once()
