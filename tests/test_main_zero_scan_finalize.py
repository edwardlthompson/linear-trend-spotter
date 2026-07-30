"""Regression tests for healthy zero-result scanner finalization."""

from __future__ import annotations

from datetime import datetime, timezone

import main as scanner_main


def test_zero_qualified_scan_publishes_exits_and_empty_snapshot(monkeypatch, tmp_path) -> None:
    class ActiveDb:
        def __init__(self) -> None:
            self.current_coins: list[dict[str, object]] | None = None
            self.registered: list[tuple[str, str, int]] = []

        def get_entered_exited(
            self,
            current_coins: list[dict[str, object]],
            cooldown_hours: int = 0,
        ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
            self.current_coins = current_coins
            return [], [{"symbol": "ABC", "name": "Example Coin", "slug": "abc"}], []

        def register_exit(self, symbol: str, reason: str = "", cooldown_hours: int = 0) -> None:
            self.registered.append((symbol, reason, cooldown_hours))

    active_db = ActiveDb()
    captured: dict[str, object] = {}
    pushed: list[tuple[object, object]] = []
    web_notified: list[tuple[object, object]] = []
    ntfy_notified: list[tuple[object, object]] = []

    monkeypatch.setattr(scanner_main.settings, "DATA_DIR", tmp_path)
    monkeypatch.setitem(scanner_main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(scanner_main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FILE", "qualified_public_snapshot.json")
    monkeypatch.setitem(scanner_main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET", "full")
    monkeypatch.setitem(scanner_main.settings._config, "SCAN_INTERVAL_SECONDS", 3600)
    monkeypatch.setitem(scanner_main.settings._config, "SCAN_HEARTBEAT_ENABLED", False)
    monkeypatch.setitem(scanner_main.settings._config, "NTFY_ENABLED", False)
    monkeypatch.setitem(scanner_main.settings._config, "ALERT_COOLDOWN_HOURS", 6)

    def fake_write_public_snapshot(data_dir: object, filename: str, final_results: list[object], **kwargs: object) -> None:
        captured["data_dir"] = data_dir
        captured["filename"] = filename
        captured["final_results"] = final_results
        captured["kwargs"] = kwargs

    monkeypatch.setattr(scanner_main, "write_public_qualified_snapshot", fake_write_public_snapshot)
    monkeypatch.setattr(
        scanner_main,
        "maybe_push_qualified_snapshot_relay",
        lambda data_dir, filename: pushed.append((data_dir, filename)),
    )
    monkeypatch.setattr(
        scanner_main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: web_notified.append((entered, exited)),
    )
    monkeypatch.setattr(
        scanner_main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: ntfy_notified.append((entered, exited)),
    )

    entered, exited, blocked = scanner_main._publish_zero_qualified_scan(
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
        all_processed_map={},
        uniformity_passed_symbols=set(),
        all_symbols_count=123,
        scan_started_at=datetime.now(timezone.utc),
    )

    assert entered == []
    assert blocked == []
    assert active_db.current_coins == []
    assert active_db.registered == [("ABC", "Missing from current CoinMarketCap snapshot", 6)]
    assert exited[0]["exit_reason"] == "Missing from current CoinMarketCap snapshot"
    assert captured["final_results"] == []
    kwargs = captured["kwargs"]
    assert kwargs["scan_health"]["coins_evaluated"] == 123  # type: ignore[index]
    assert kwargs["qualification_exits"] == exited  # type: ignore[index]
    assert pushed == [(tmp_path, "qualified_public_snapshot.json")]
    assert web_notified == [([], exited)]
    assert ntfy_notified == [([], exited)]
