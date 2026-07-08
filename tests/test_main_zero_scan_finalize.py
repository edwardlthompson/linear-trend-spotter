"""Regression coverage for healthy zero-qualified scanner runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import main as scanner_main


class _Closer:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ActiveDB:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, Any]], int]] = []
        self.exited = [{"symbol": "ABC", "name": "Alpha"}]

    def get_entered_exited(
        self,
        current_coins: list[dict[str, Any]],
        *,
        cooldown_hours: int = 0,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        self.calls.append((current_coins, cooldown_hours))
        return [], self.exited, []


def test_zero_qualified_scan_finalizes_exits_snapshot_and_notifications(monkeypatch) -> None:
    active_db = _ActiveDB()
    tv_mapper = _Closer()
    exchange_db = _Closer()
    cg_mapper = _Closer()
    cache = _Closer()
    captured: dict[str, Any] = {}

    def fake_attach_exit_reasons(exited: list[dict[str, Any]], **kwargs: Any) -> None:
        captured["attach_exited"] = exited
        captured["all_processed_map"] = kwargs["all_processed_map"]
        captured["uniformity_passed_symbols"] = kwargs["uniformity_passed_symbols"]
        for row in exited:
            row["exit_reason"] = "Failed gain/volume filter"

    def fake_publish(final_results: list[dict[str, Any]], **kwargs: Any) -> None:
        captured["published_final_results"] = final_results
        captured["published_exited"] = kwargs["exited"]

    monkeypatch.setattr(scanner_main, "attach_exit_reasons_and_register", fake_attach_exit_reasons)
    monkeypatch.setattr(scanner_main, "_publish_public_snapshot", fake_publish)
    monkeypatch.setattr(
        scanner_main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: captured.setdefault("web_push", (entered, exited)),
    )
    monkeypatch.setattr(
        scanner_main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: captured.setdefault("ntfy", (entered, exited)),
    )

    scanner_main._finalize_zero_qualified_scan(
        active_db=active_db,
        tv_mapper=tv_mapper,
        exchange_db=exchange_db,
        cg_mapper=cg_mapper,
        cache=cache,
        scan_started_at=datetime.now(timezone.utc),
        all_symbols=["ABC"],
        all_symbols_set={"ABC"},
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

    assert active_db.calls == [([], scanner_main.settings.alert_cooldown_hours)]
    assert captured["attach_exited"] is active_db.exited
    assert captured["all_processed_map"] == {}
    assert captured["uniformity_passed_symbols"] == set()
    assert captured["published_final_results"] == []
    assert captured["published_exited"] is active_db.exited
    assert captured["web_push"] == ([], active_db.exited)
    assert captured["ntfy"] == ([], active_db.exited)
    assert tv_mapper.closed and exchange_db.closed and cg_mapper.closed and cache.closed
