"""Zero-qualified scan finalization regressions."""

from __future__ import annotations

from datetime import datetime, timezone

import main


class FakeActiveDb:
    def __init__(self) -> None:
        self.current_rows: list[list[dict[str, object]]] = []

    def get_entered_exited(
        self, current_coins: list[dict[str, object]], *, cooldown_hours: int
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
        self.current_rows.append(current_coins)
        return [], [{"symbol": "ABC"}], []


def test_zero_qualified_scan_publishes_empty_snapshot_and_exit_notifications(monkeypatch, tmp_path) -> None:
    active_db = FakeActiveDb()
    captured: dict[str, object] = {}

    monkeypatch.setattr(main.settings, "DATA_DIR", tmp_path)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FILE", "snapshot.json")
    monkeypatch.setitem(main.settings._config, "NTFY_ENABLED", True)
    monkeypatch.setitem(main.settings._config, "NTFY_BASE_URL", "https://ntfy.sh")
    monkeypatch.setitem(main.settings._config, "NTFY_TOPIC", "topic1")

    def fake_attach(exited: list[dict[str, object]], **kwargs: object) -> None:
        captured["attach_exited"] = exited
        captured["all_processed_map"] = kwargs["all_processed_map"]
        captured["uniformity_passed_symbols"] = kwargs["uniformity_passed_symbols"]
        for coin in exited:
            coin["exit_reason"] = "Failed gain/volume filter"

    def fake_write_snapshot(
        data_dir: object,
        filename: str,
        final_results: list[dict[str, object]],
        **kwargs: object,
    ) -> None:
        captured["snapshot"] = {
            "data_dir": data_dir,
            "filename": filename,
            "final_results": final_results,
            "qualification_exits": kwargs["qualification_exits"],
            "notify_public_config": kwargs["notify_public_config"],
        }

    monkeypatch.setattr(main, "attach_exit_reasons_and_register", fake_attach)
    monkeypatch.setattr(main, "write_public_qualified_snapshot", fake_write_snapshot)
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *args: captured.setdefault("relay", args))
    monkeypatch.setattr(
        main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: captured.setdefault("web_push", (entered, exited)),
    )
    monkeypatch.setattr(
        main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: captured.setdefault("ntfy", (entered, exited)),
    )

    main._finalize_zero_qualified_scan(
        scan_started_at=datetime.now(timezone.utc),
        active_db=active_db,
        all_symbols_set={"ABC"},
        top_coins_provider="cmc",
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gecko=object(),
        alias_markets_by_id={},
        gain_qualified_symbols=set(),
        coins_with_cg_ids_symbols=set(),
        coins_evaluated=1,
    )

    assert active_db.current_rows == [[]]
    assert captured["all_processed_map"] == {}
    assert captured["uniformity_passed_symbols"] == set()
    snapshot = captured["snapshot"]
    assert snapshot["filename"] == "snapshot.json"
    assert snapshot["final_results"] == []
    assert snapshot["qualification_exits"] == [{"symbol": "ABC", "exit_reason": "Failed gain/volume filter"}]
    assert snapshot["notify_public_config"] == {"ntfy_subscribe_url": "https://ntfy.sh/topic1"}
    assert captured["web_push"] == ([], snapshot["qualification_exits"])
    assert captured["ntfy"] == ([], snapshot["qualification_exits"])
