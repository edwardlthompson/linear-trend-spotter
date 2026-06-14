from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import main


def _snapshot_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        DATA_DIR=tmp_path,
        public_qualified_snapshot_enabled=True,
        public_qualified_snapshot_file="qualified_public_snapshot.json",
        public_qualified_snapshot_field_set="full",
        scan_interval_seconds=3600,
        scan_cost_panel_coingecko_monthly_http_cap=0,
        scan_cost_panel_polygon_monthly_http_cap=0,
        scan_cost_panel_cmc_monthly_http_cap=0,
        cmc_api_key="",
        db_paths={"scanner": tmp_path / "scanner.db"},
    )


def test_publish_public_snapshot_writes_empty_rows_with_exits(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(main, "fetch_vendor_quotas", lambda **_: {})
    pushed: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        main,
        "maybe_push_qualified_snapshot_relay",
        lambda data_dir, filename: pushed.append((data_dir, filename)),
    )

    main._publish_public_snapshot(
        settings_obj=_snapshot_settings(tmp_path),
        scan_started_at=datetime.now(timezone.utc),
        final_results=[],
        all_symbols_count=42,
        qualification_exits=[{"symbol": "abc", "exit_reason": "7d gain below threshold"}],
    )

    payload = json.loads((tmp_path / "qualified_public_snapshot.json").read_text(encoding="utf-8"))
    assert payload["coins"] == []
    assert payload["coins_evaluated"] == 42
    assert payload["qualification_exits"] == [
        {"symbol": "ABC", "exit_reason": "7d gain below threshold"}
    ]
    assert pushed == [(tmp_path, "qualified_public_snapshot.json")]


def test_finalize_zero_qualified_scan_clears_active_and_publishes_exits(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    class ActiveDbStub:
        def __init__(self) -> None:
            self.current_rows: list[list[dict[str, Any]]] = []

        def get_entered_exited(
            self,
            current_coins: list[dict[str, Any]],
            cooldown_hours: int = 0,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
            self.current_rows.append(current_coins)
            return [], [{"symbol": "ABC", "name": "Alpha", "slug": "alpha"}], []

    active_db = ActiveDbStub()
    settings_obj = SimpleNamespace(alert_cooldown_hours=6, metrics_file=tmp_path / "metrics.json")
    published: list[dict[str, Any]] = []
    notified: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    def fake_attach_exit_reasons(exited: list[dict[str, Any]], **_: Any) -> None:
        for row in exited:
            row["exit_reason"] = "7d gain below threshold"

    def fake_publish(**kwargs: Any) -> None:
        published.append(kwargs)

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", fake_attach_exit_reasons)
    monkeypatch.setattr(main, "_publish_public_snapshot", fake_publish)
    monkeypatch.setattr(
        main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: notified.append((entered, exited)),
    )
    monkeypatch.setattr(main.metrics, "save", lambda path: None)

    main._finalize_zero_qualified_scan(
        active_db=active_db,
        settings_obj=settings_obj,
        scan_started_at=datetime.now(timezone.utc),
        all_symbols=["ABC", "XYZ"],
        all_symbols_set={"ABC", "XYZ"},
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

    assert active_db.current_rows == [[]]
    assert published
    assert published[0]["final_results"] == []
    assert published[0]["all_symbols_count"] == 2
    assert published[0]["qualification_exits"] == [
        {"symbol": "ABC", "name": "Alpha", "slug": "alpha", "exit_reason": "7d gain below threshold"}
    ]
    assert notified == [([], published[0]["qualification_exits"])]
