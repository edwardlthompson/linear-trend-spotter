"""Regression tests for healthy zero-result scanner finalization."""

from __future__ import annotations

from types import SimpleNamespace

import main


class _Closeable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeActiveDb:
    def __init__(self) -> None:
        self.current_rows = None

    def get_active(self) -> dict:
        return {"BTC": {"symbol": "BTC"}}

    def get_entered_exited(self, current_rows: list, *, cooldown_hours: int = 0) -> tuple:
        self.current_rows = current_rows
        return [], [{"symbol": "BTC"}], []


class _FakeSettings:
    def __init__(self, tmp_path) -> None:
        self.DATA_DIR = tmp_path
        self.base_dir = tmp_path
        self.db_paths = {"exchanges": tmp_path / "exchanges.db", "scanner": tmp_path / "scanner.db"}
        self.metrics_file = tmp_path / "metrics.json"
        self.exit_analytics_file = tmp_path / "exit_reason_analytics.json"
        self.scanner_insights_file = tmp_path / "scanner_insights.json"
        self.min_volume = 1_000_000
        self.gain_filter_min_7d_percent = 7.0
        self.gain_filter_min_30d_percent = 30.0
        self.uniformity_min_score = 55
        self.target_exchanges = ["coinbase", "kraken"]
        self.artifact_hygiene_enabled = False
        self.top_coins_provider = "cmc"
        self.top_coins_limit = 10
        self.cmc_symbol_aliases = {}
        self.coingecko_id_aliases = {}
        self.alert_cooldown_hours = 6
        self.scan_heartbeat_enabled = False
        self.public_qualified_snapshot_enabled = True
        self.public_qualified_snapshot_file = "qualified_public_snapshot.json"
        self.public_qualified_snapshot_field_set = "full"
        self.scan_interval_seconds = 3600
        self.cmc_api_key = ""
        self.scan_cost_panel_coingecko_monthly_http_cap = 0
        self.scan_cost_panel_polygon_monthly_http_cap = 0
        self.scan_cost_panel_cmc_monthly_http_cap = 0
        self.ntfy_enabled = False
        self.ntfy_base_url = "https://ntfy.sh"
        self.ntfy_topic = ""
        self.portfolio_sim_starting_capital = 1000


def _install_common_fakes(monkeypatch, tmp_path, *, gain_rows: list[dict], cg_rows: list[dict]) -> dict:
    fake_settings = _FakeSettings(tmp_path)
    fake_active = _FakeActiveDb()
    runtime = {
        "history_db": SimpleNamespace(),
        "active_db": fake_active,
        "cache": _Closeable(),
        "exchange_db": _Closeable(),
        "tv_mapper": _Closeable(),
        "cmc": object(),
        "gecko": object(),
        "history_fallback": object(),
        "cg_mapper": _Closeable(),
        "cmc_slug_resolver": object(),
    }
    calls: dict[str, object] = {"snapshot": None, "web_notify": None, "ntfy_notify": None, "exit_args": None}

    top_dataset = SimpleNamespace(
        all_cmc_coins=[],
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )

    monkeypatch.setattr(main, "settings", fake_settings)
    monkeypatch.setattr(main, "initialize_runtime_components", lambda _settings: runtime)
    monkeypatch.setattr(main, "fetch_top_coins_dataset", lambda **_kwargs: top_dataset)
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *_args, **_kwargs: (["BTC"], {"BTC"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **_kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **_kwargs: None)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *_args, **_kwargs: gain_rows)
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *_args, **_kwargs: (cg_rows, []))
    monkeypatch.setattr(main, "fetch_vendor_quotas", lambda **_kwargs: {})
    monkeypatch.setattr(main, "build_api_cost_panel_for_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "update_exit_reason_analytics", lambda *_args, **_kwargs: {"last_run": {"exits": 1}, "total_exits": 1})
    monkeypatch.setattr(main, "update_scanner_insights", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        main,
        "attach_exit_reasons_and_register",
        lambda exited, **kwargs: calls.update({"exit_args": kwargs}) or exited[0].update({"exit_reason": "regressed out"}),
    )
    monkeypatch.setattr(
        main,
        "write_public_qualified_snapshot",
        lambda *_args, **kwargs: calls.update({"snapshot": kwargs}),
    )
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: calls.update({"web_notify": (entered, exited)}),
    )
    monkeypatch.setattr(
        main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: calls.update({"ntfy_notify": (entered, exited)}),
    )
    return {"active": fake_active, "runtime": runtime, "calls": calls}


def test_no_gain_results_finalize_exits_snapshot_and_notifications(monkeypatch, tmp_path) -> None:
    ctx = _install_common_fakes(monkeypatch, tmp_path, gain_rows=[], cg_rows=[])

    main.run_scanner()

    assert ctx["active"].current_rows == []
    assert ctx["calls"]["snapshot"]["qualification_exits"] == [{"symbol": "BTC", "exit_reason": "regressed out"}]
    assert ctx["calls"]["web_notify"] == ([], [{"symbol": "BTC", "exit_reason": "regressed out"}])
    assert ctx["calls"]["ntfy_notify"] == ([], [{"symbol": "BTC", "exit_reason": "regressed out"}])
    assert ctx["runtime"]["cache"].closed is True


def test_no_coingecko_ids_finalize_exits_snapshot_and_notifications(monkeypatch, tmp_path) -> None:
    gain_rows = [{"symbol": "BTC", "name": "Bitcoin", "gains": {"7d": 10, "30d": 40}}]
    ctx = _install_common_fakes(monkeypatch, tmp_path, gain_rows=gain_rows, cg_rows=[])

    main.run_scanner()

    assert ctx["active"].current_rows == []
    assert ctx["calls"]["snapshot"]["qualification_exits"] == [{"symbol": "BTC", "exit_reason": "regressed out"}]
    assert ctx["calls"]["exit_args"]["gain_qualified_symbols"] == {"BTC"}
    assert ctx["calls"]["exit_args"]["coins_with_cg_ids_symbols"] == set()
