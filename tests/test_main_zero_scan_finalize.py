"""Regression coverage for healthy scanner runs with zero qualified rows."""

from __future__ import annotations

from unittest.mock import MagicMock

import main
from scanner.top_coins_stage import TopCoinsDataset


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ActiveDb:
    def __init__(self, exited: list[dict[str, object]]) -> None:
        self.exited = exited
        self.calls: list[tuple[list[dict[str, object]], int]] = []

    def get_entered_exited(
        self,
        current_coins: list[dict[str, object]],
        cooldown_hours: int = 0,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
        self.calls.append((current_coins, cooldown_hours))
        return [], self.exited, []


def _dataset() -> TopCoinsDataset:
    cmc_by_symbol = {
        "OLD": {
            "data": {},
            "gains": {"7d": 1.0, "30d": 2.0},
            "info": {"symbol": "OLD", "volume_24h": 2_000_000},
        }
    }
    return TopCoinsDataset(
        all_cmc_coins=list(cmc_by_symbol.values()),
        cmc_by_symbol=cmc_by_symbol,
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )


def _runtime(active_db: _ActiveDb) -> dict[str, object]:
    return {
        "history_db": MagicMock(),
        "active_db": active_db,
        "cache": _Closable(),
        "exchange_db": _Closable(),
        "tv_mapper": _Closable(),
        "cmc": MagicMock(),
        "gecko": MagicMock(),
        "history_fallback": MagicMock(),
        "cg_mapper": _Closable(),
        "cmc_slug_resolver": MagicMock(),
    }


def _patch_common(monkeypatch, active_db: _ActiveDb) -> dict[str, object]:
    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FILE", "snapshot.json")
    monkeypatch.setitem(main.settings._config, "ALERT_COOLDOWN_HOURS", 6)
    monkeypatch.setitem(main.settings._config, "TOP_COINS_PROVIDER", "cmc")

    runtime = _runtime(active_db)
    monkeypatch.setattr(main, "initialize_runtime_components", lambda _settings: runtime)
    monkeypatch.setattr(main, "fetch_top_coins_dataset", MagicMock(return_value=_dataset()))
    monkeypatch.setattr(
        main,
        "load_exchange_symbol_universe",
        MagicMock(return_value=(["OLD"], {"OLD"})),
    )
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", MagicMock(return_value={}))
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", MagicMock())
    monkeypatch.setattr(main, "attach_target_exchange_listings", MagicMock())
    monkeypatch.setattr(main, "fetch_vendor_quotas", MagicMock(return_value={}))
    monkeypatch.setattr(main, "build_api_cost_panel_for_snapshot", MagicMock(return_value={"sources": []}))
    monkeypatch.setattr(main, "write_public_qualified_snapshot", MagicMock())
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", MagicMock())
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", MagicMock())
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", MagicMock())

    def _attach_reasons(exited: list[dict[str, object]], **_kwargs: object) -> None:
        for coin in exited:
            coin["exit_reason"] = "Failed gain/volume filter"

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", MagicMock(side_effect=_attach_reasons))
    return runtime


def test_zero_gain_scan_finalizes_exits_and_empty_snapshot(monkeypatch) -> None:
    active_db = _ActiveDb([{"symbol": "OLD", "name": "Old Coin"}])
    _patch_common(monkeypatch, active_db)
    monkeypatch.setattr(main, "apply_gain_volume_filter", MagicMock(return_value=[]))
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", MagicMock())

    main.run_scanner()

    assert active_db.calls == [([], 6)]
    main.attach_exit_reasons_and_register.assert_called_once()
    main.write_public_qualified_snapshot.assert_called_once()
    snapshot_args = main.write_public_qualified_snapshot.call_args
    assert snapshot_args.args[2] == []
    assert snapshot_args.kwargs["qualification_exits"] == [
        {"symbol": "OLD", "name": "Old Coin", "exit_reason": "Failed gain/volume filter"}
    ]
    main.maybe_push_qualified_snapshot_relay.assert_called_once()
    main.maybe_notify_web_push_qualified_changes.assert_called_once_with(
        [],
        [{"symbol": "OLD", "name": "Old Coin", "exit_reason": "Failed gain/volume filter"}],
    )
    main.maybe_notify_ntfy_qualified_changes.assert_called_once()
    main.attach_coin_gecko_ids_and_learn.assert_not_called()


def test_zero_coin_gecko_id_scan_finalizes_after_gain_stage(monkeypatch) -> None:
    active_db = _ActiveDb([{"symbol": "OLD", "name": "Old Coin"}])
    _patch_common(monkeypatch, active_db)
    gain_rows = [{"symbol": "OLD", "name": "Old Coin", "gains": {"7d": 8.0, "30d": 40.0}}]
    monkeypatch.setattr(main, "apply_gain_volume_filter", MagicMock(return_value=gain_rows))
    monkeypatch.setattr(
        main,
        "attach_coin_gecko_ids_and_learn",
        MagicMock(return_value=([], gain_rows)),
    )
    monkeypatch.setattr(main, "compute_uniformities_from_ohlcv", MagicMock())

    main.run_scanner()

    assert active_db.calls == [([], 6)]
    main.attach_exit_reasons_and_register.assert_called_once()
    assert main.attach_exit_reasons_and_register.call_args.kwargs["gain_qualified_symbols"] == {"OLD"}
    assert main.attach_exit_reasons_and_register.call_args.kwargs["coins_with_cg_ids_symbols"] == set()
    main.write_public_qualified_snapshot.assert_called_once()
    assert main.write_public_qualified_snapshot.call_args.args[2] == []
    main.maybe_notify_web_push_qualified_changes.assert_called_once()
    main.maybe_notify_ntfy_qualified_changes.assert_called_once()
    main.compute_uniformities_from_ohlcv.assert_not_called()
