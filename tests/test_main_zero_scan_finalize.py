from datetime import datetime, timezone

import main


class FakeActiveDb:
    def __init__(self) -> None:
        self.registered: list[tuple[str, str, int]] = []

    def get_entered_exited(self, current_coins, cooldown_hours: int = 0):
        assert current_coins == []
        return [], [{"symbol": "OLD", "name": "Old Coin", "slug": "old"}], []

    def register_exit(self, symbol: str, reason: str = "", cooldown_hours: int = 0) -> None:
        self.registered.append((symbol, reason, cooldown_hours))


def test_zero_qualified_scan_publishes_exits_and_notifies(monkeypatch, tmp_path) -> None:
    active_db = FakeActiveDb()
    snapshots: list[dict] = []
    web_push_calls: list[tuple[list, list]] = []
    ntfy_calls: list[tuple[list, list]] = []

    monkeypatch.setattr(main.settings, "DATA_DIR", tmp_path)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FILE", "qualified.json")
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET", "full")
    monkeypatch.setitem(main.settings._config, "SCAN_HEARTBEAT_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "ALERT_COOLDOWN_HOURS", 6)
    monkeypatch.setitem(main.settings._config, "NTFY_ENABLED", False)

    def fake_write_snapshot(*args, **kwargs):
        snapshots.append(
            {
                "final_results": args[2],
                "qualification_exits": kwargs["qualification_exits"],
                "scan_health": kwargs["scan_health"],
            }
        )

    monkeypatch.setattr(main, "write_public_qualified_snapshot", fake_write_snapshot)
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main,
        "update_exit_reason_analytics",
        lambda *_args, **_kwargs: {"last_run": {"exits": 1}, "total_exits": 1},
    )
    monkeypatch.setattr(main.metrics, "save", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: web_push_calls.append((entered, exited)),
    )
    monkeypatch.setattr(
        main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: ntfy_calls.append((entered, exited)),
    )

    main._publish_zero_qualified_scan(
        active_db=active_db,
        scan_started_at=datetime.now(timezone.utc),
        reason="no_gain_qualified",
        all_symbols=["OLD"],
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

    assert active_db.registered == [("OLD", "Missing from current CoinMarketCap snapshot", 6)]
    assert snapshots[0]["final_results"] == []
    assert snapshots[0]["qualification_exits"][0]["symbol"] == "OLD"
    assert snapshots[0]["qualification_exits"][0]["exit_reason"] == "Missing from current CoinMarketCap snapshot"
    assert snapshots[0]["scan_health"]["coins_evaluated"] == 1
    assert web_push_calls[0][1][0]["symbol"] == "OLD"
    assert ntfy_calls[0][1][0]["symbol"] == "OLD"
