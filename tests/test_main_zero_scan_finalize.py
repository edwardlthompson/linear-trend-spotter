"""Regression coverage for healthy scans with zero qualified finalists."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import main


def _settings(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        DATA_DIR=tmp_path,
        alert_cooldown_hours=6,
        public_qualified_snapshot_enabled=True,
        public_qualified_snapshot_file="qualified_public_snapshot.json",
        public_qualified_snapshot_field_set="full",
        scan_interval_seconds=3600,
        ntfy_enabled=True,
        ntfy_base_url="https://ntfy.sh",
        ntfy_topic="topic1",
    )


class _ActiveDb:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def get_entered_exited(self, current_coins, cooldown_hours=0):
        self.calls.append(list(current_coins))
        return [], [{"symbol": "OLD", "name": "Old", "slug": "old"}], []


def test_finalize_zero_scan_publishes_empty_snapshot_and_notifies(monkeypatch, tmp_path) -> None:
    active_db = _ActiveDb()
    snapshot_calls: list[dict] = []
    web_push_calls: list[tuple[list, list]] = []
    ntfy_calls: list[tuple[list, list]] = []

    def fake_attach(exited, **_kwargs) -> None:
        for coin in exited:
            coin["exit_reason"] = "Failed gain/volume filter"

    def fake_write(data_dir, filename, rows, **kwargs) -> None:
        snapshot_calls.append({"data_dir": data_dir, "filename": filename, "rows": rows, "kwargs": kwargs})

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", fake_attach)
    monkeypatch.setattr(main, "write_public_qualified_snapshot", fake_write)
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *_args: None)
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", lambda ent, ext: web_push_calls.append((ent, ext)))
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", lambda ent, ext: ntfy_calls.append((ent, ext)))

    main._finalize_zero_qualified_scan(
        scan_started_at=datetime.now(timezone.utc),
        active_db=active_db,
        settings_obj=_settings(tmp_path),
        all_symbols_set={"OLD"},
        top_coins_provider="cmc",
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gecko=None,
        alias_markets_by_id={},
        gain_qualified_symbols=set(),
        coins_with_cg_ids_symbols=set(),
    )

    assert active_db.calls == [[]]
    assert snapshot_calls[0]["rows"] == []
    assert snapshot_calls[0]["kwargs"]["qualification_exits"][0]["symbol"] == "OLD"
    assert snapshot_calls[0]["kwargs"]["notify_public_config"]["ntfy_subscribe_url"] == "https://ntfy.sh/topic1"
    assert web_push_calls[0][1][0]["symbol"] == "OLD"
    assert ntfy_calls[0][1][0]["symbol"] == "OLD"


def test_run_scanner_finalizes_when_gain_filter_returns_zero(monkeypatch, tmp_path) -> None:
    class Closer:
        def close(self) -> None:
            pass

    fake_settings = SimpleNamespace(
        artifact_hygiene_enabled=False,
        min_volume=1_000_000,
        uniformity_min_score=55,
        target_exchanges=["coinbase", "kraken"],
        db_paths={"exchanges": tmp_path / "exchanges.db"},
        top_coins_provider="cmc",
        top_coins_limit=10,
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gain_filter_min_7d_percent=7.0,
        gain_filter_min_30d_percent=30.0,
    )
    runtime = {
        "history_db": Closer(),
        "active_db": object(),
        "cache": Closer(),
        "exchange_db": Closer(),
        "tv_mapper": Closer(),
        "cmc": object(),
        "gecko": object(),
        "history_fallback": object(),
        "cg_mapper": Closer(),
        "cmc_slug_resolver": None,
    }
    finalize_calls: list[dict] = []

    monkeypatch.setattr(main, "settings", fake_settings)
    monkeypatch.setattr(main, "initialize_runtime_components", lambda _settings: runtime)
    monkeypatch.setattr(
        main,
        "fetch_top_coins_dataset",
        lambda **_kwargs: SimpleNamespace(
            all_cmc_coins=[],
            cmc_by_symbol={},
            cmc_by_normalized_symbol={},
            cmc_symbol_aliases={},
            coingecko_id_aliases={},
        ),
    )
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *_args, **_kwargs: (["OLD"], {"OLD"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **_kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **_kwargs: None)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "_finalize_zero_qualified_scan", lambda **kwargs: finalize_calls.append(kwargs))

    main.run_scanner()

    assert len(finalize_calls) == 1
    assert finalize_calls[0]["all_symbols_set"] == {"OLD"}
    assert finalize_calls[0]["reason"] == "no coins passed gain filter"
