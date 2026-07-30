"""Regression coverage for healthy scans that produce zero qualified coins."""

from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


class _Metrics:
    def reset(self) -> None:
        pass

    def get_summary(self) -> dict:
        return {"errors": {}}

    def report(self) -> str:
        return ""

    def increment(self, *_args, **_kwargs) -> None:
        pass

    def save(self, *_args, **_kwargs) -> None:
        pass


class _Logger:
    def info(self, *_args, **_kwargs) -> None:
        pass

    def warning(self, *_args, **_kwargs) -> None:
        pass

    def error(self, *_args, **_kwargs) -> None:
        pass

    def debug(self, *_args, **_kwargs) -> None:
        pass


def _module(name: str, **attrs: object) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, val in attrs.items():
        setattr(mod, key, val)
    return mod


@pytest.fixture()
def main_module(monkeypatch):
    """Import main.py with heavyweight data/backtest modules stubbed for control-flow tests."""
    stubs = {
        "backtesting.data_loader": _module("backtesting.data_loader", BacktestDataLoader=object),
        "backtesting.runner": _module("backtesting.runner", run_backtests_for_final_results=lambda *_a, **_k: {}),
        "backtesting.params": _module("backtesting.params", runner_params_from_settings=lambda: object()),
        "backtesting.report": _module("backtesting.report", notification_rows_for_symbol=lambda *_a, **_k: {}),
        "utils.insights": _module(
            "utils.insights",
            compute_health_score=lambda *_a, **_k: None,
            compute_reentry_quality=lambda *_a, **_k: {},
            update_scanner_insights=lambda *_a, **_k: {},
        ),
        "utils.metrics": _module("utils.metrics", metrics=_Metrics(), timed_block=lambda _name: _ClosableContext()),
        "utils.runtime_hygiene": _module(
            "utils.runtime_hygiene",
            run_artifact_hygiene=lambda *_a, **_k: {},
            update_exit_reason_analytics=lambda *_a, **_k: {"last_run": {"exits": 0}},
        ),
        "utils.cross_provider_identity": _module(
            "utils.cross_provider_identity", attach_identity_bundles=lambda *_a, **_k: None
        ),
        "utils.scan_artifacts": _module(
            "utils.scan_artifacts",
            build_notify_public_config=lambda **_k: None,
            write_public_qualified_snapshot=lambda *_a, **_k: None,
            write_scan_heartbeat=lambda *_a, **_k: None,
        ),
        "utils.scan_costs": _module(
            "utils.scan_costs",
            build_api_cost_panel_for_snapshot=lambda *_a, **_k: None,
            read_last_completed_coingecko_http_total=lambda *_a, **_k: None,
            write_scan_costs_file=lambda *_a, **_k: None,
        ),
        "utils.vendor_api_quota": _module("utils.vendor_api_quota", fetch_vendor_quotas=lambda *_a, **_k: {}),
        "utils.watchlist_export": _module(
            "utils.watchlist_export",
            compute_watchlist_rows=lambda *_a, **_k: [],
            write_watchlist_exports=lambda *_a, **_k: None,
        ),
        "utils.portfolio_multi": _module(
            "utils.portfolio_multi", write_multi_portfolio_simulation=lambda *_a, **_k: None
        ),
        "utils.alert_backtest_report": _module(
            "utils.alert_backtest_report", write_alert_backtest_report=lambda *_a, **_k: None
        ),
        "utils.backtest_strategy_diff": _module(
            "utils.backtest_strategy_diff", save_top_strategy_state=lambda *_a, **_k: None
        ),
        "utils.logger": _module(
            "utils.logger", app_logger=_Logger(), maybe_install_structured_json_handler=lambda: None
        ),
        "scanner.coin_enrichment": _module(
            "scanner.coin_enrichment",
            SPARKLINE_HOURLY_MAX_BARS=720,
            attach_hourly_sparkline_closes_for_snapshot=lambda *_a, **_k: None,
            attach_rank_movement=lambda *_a, **_k: None,
            attach_signal_age=lambda *_a, **_k: None,
            attach_volume_acceleration=lambda *_a, **_k: None,
        ),
        "scanner.web_push_notify": _module(
            "scanner.web_push_notify", maybe_notify_web_push_qualified_changes=lambda *_a, **_k: None
        ),
        "scanner.ntfy_notify": _module(
            "scanner.ntfy_notify", maybe_notify_ntfy_qualified_changes=lambda *_a, **_k: None
        ),
        "scanner.snapshot_relay_notify": _module(
            "scanner.snapshot_relay_notify", maybe_push_qualified_snapshot_relay=lambda *_a, **_k: None
        ),
        "scanner.runtime_init": _module("scanner.runtime_init", initialize_runtime_components=lambda *_a, **_k: {}),
        "scanner.top_coin_resolution": _module(
            "scanner.top_coin_resolution", ensure_cmc_notify_urls=lambda *_a, **_k: None
        ),
        "scanner.top_coins_stage": _module("scanner.top_coins_stage", fetch_top_coins_dataset=lambda **_k: None),
        "scanner.exchange_universe": _module(
            "scanner.exchange_universe", load_exchange_symbol_universe=lambda *_a, **_k: ([], set())
        ),
        "scanner.coingecko_alias_prefetch": _module(
            "scanner.coingecko_alias_prefetch",
            prefetch_alias_markets_by_gecko_id=lambda **_k: {},
            top_up_alias_markets_for_symbols=lambda **_k: None,
        ),
        "scanner.gain_volume_filter": _module("scanner.gain_volume_filter", apply_gain_volume_filter=lambda *_a, **_k: []),
        "scanner.listings_and_volumes": _module(
            "scanner.listings_and_volumes",
            attach_coin_gecko_ids_and_learn=lambda *_a, **_k: ([], []),
            attach_target_exchange_listings=lambda *_a, **_k: None,
            hydrate_exchange_volumes_from_coingecko=lambda *_a, **_k: 0,
        ),
        "scanner.uniformity_stages": _module(
            "scanner.uniformity_stages",
            apply_uniformity_pass_and_regime=lambda *_a, **_k: ([], set(), None),
            compute_uniformities_from_ohlcv=lambda *_a, **_k: ([], {}, []),
        ),
        "scanner.exit_pipeline": _module(
            "scanner.exit_pipeline", attach_exit_reasons_and_register=lambda *_a, **_k: None
        ),
        "exchange_data.exchange_fetcher": _module("exchange_data.exchange_fetcher", ExchangeFetcher=object),
    }
    for name, mod in stubs.items():
        monkeypatch.setitem(sys.modules, name, mod)
    sys.modules.pop("main", None)
    mod = importlib.import_module("main")
    yield mod
    sys.modules.pop("main", None)


class _ClosableContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        pass


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


def _install_common_scan_mocks(monkeypatch, main, active_db: _ActiveDb) -> None:
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


def test_no_gain_qualified_scan_finalizes_exits_and_publishes_empty_snapshot(monkeypatch, main_module) -> None:
    main = main_module
    active_db = _ActiveDb()
    _install_common_scan_mocks(monkeypatch, main, active_db)
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


def test_no_coingecko_ids_scan_still_finalizes_exits(monkeypatch, main_module) -> None:
    main = main_module
    active_db = _ActiveDb()
    _install_common_scan_mocks(monkeypatch, main, active_db)
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
