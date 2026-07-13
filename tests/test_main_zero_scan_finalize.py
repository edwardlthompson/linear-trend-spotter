"""Regression tests for healthy zero-result scanner finalization."""

from __future__ import annotations

from types import SimpleNamespace

import main


class _Closer:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _runtime(active_db: object | None = None) -> dict[str, object]:
    return {
        "history_db": object(),
        "active_db": active_db or object(),
        "cache": _Closer(),
        "exchange_db": _Closer(),
        "tv_mapper": _Closer(),
        "cmc": object(),
        "gecko": object(),
        "history_fallback": object(),
        "cg_mapper": _Closer(),
        "cmc_slug_resolver": object(),
    }


def _top_dataset() -> SimpleNamespace:
    return SimpleNamespace(
        all_cmc_coins=[],
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
    )


def _patch_common(monkeypatch, runtime: dict[str, object]) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setattr(main, "initialize_runtime_components", lambda settings: runtime)
    monkeypatch.setattr(main, "fetch_top_coins_dataset", lambda **kwargs: _top_dataset())
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *a, **k: (["ABC"], {"ABC"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **kwargs: None)
    monkeypatch.setattr(main, "_finalize_zero_qualified_scan", lambda **kwargs: calls.append(kwargs))
    return calls


def test_run_scanner_finalizes_when_gain_filter_has_no_results(monkeypatch) -> None:
    runtime = _runtime()
    calls = _patch_common(monkeypatch, runtime)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *a, **k: [])

    main.run_scanner()

    assert len(calls) == 1
    assert calls[0]["gain_qualified_symbols"] == set()
    assert calls[0]["coins_with_cg_ids_symbols"] == set()
    assert runtime["exchange_db"].closed
    assert runtime["tv_mapper"].closed
    assert runtime["cg_mapper"].closed


def test_run_scanner_finalizes_when_no_coingecko_ids(monkeypatch) -> None:
    runtime = _runtime()
    calls = _patch_common(monkeypatch, runtime)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *a, **k: [{"symbol": "ABC"}])
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *a, **k: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *a, **k: ([], [{"symbol": "ABC"}]))

    main.run_scanner()

    assert len(calls) == 1
    assert calls[0]["gain_qualified_symbols"] == {"ABC"}
    assert calls[0]["coins_with_cg_ids_symbols"] == set()


def test_finalize_zero_scan_publishes_exits_and_empty_snapshot(monkeypatch) -> None:
    class ActiveDb:
        def __init__(self) -> None:
            self.registered: list[tuple[str, str, int]] = []

        def get_entered_exited(self, current, cooldown_hours):
            assert current == []
            return [], [{"symbol": "ABC"}], []

        def register_exit(self, symbol, reason="", cooldown_hours=0):
            self.registered.append((symbol, reason, cooldown_hours))

    active_db = ActiveDb()
    snapshots: list[dict[str, object]] = []
    web_calls: list[tuple[object, object]] = []
    ntfy_calls: list[tuple[object, object]] = []
    monkeypatch.setattr(main, "fetch_vendor_quotas", lambda **kwargs: {})
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *a, **k: None)
    monkeypatch.setattr(main, "write_public_qualified_snapshot", lambda *a, **k: snapshots.append({"args": a, "kwargs": k}))
    monkeypatch.setattr(main, "maybe_notify_web_push_qualified_changes", lambda entered, exited: web_calls.append((entered, exited)))
    monkeypatch.setattr(main, "maybe_notify_ntfy_qualified_changes", lambda entered, exited: ntfy_calls.append((entered, exited)))
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)

    main._finalize_zero_qualified_scan(
        active_db=active_db,
        all_symbols_set=set(),
        top_coins_provider="cmc",
        cmc_by_symbol={},
        cmc_by_normalized_symbol={},
        cmc_symbol_aliases={},
        coingecko_id_aliases={},
        gecko=object(),
        alias_markets_by_id={},
        gain_qualified_symbols=set(),
        coins_with_cg_ids_symbols=set(),
        scan_started_at=main.datetime.now(main.timezone.utc),
    )

    assert active_db.registered[0][0] == "ABC"
    assert snapshots[0]["args"][2] == []
    assert snapshots[0]["kwargs"]["qualification_exits"][0]["symbol"] == "ABC"
    assert web_calls[0][1][0]["symbol"] == "ABC"
    assert ntfy_calls[0][1][0]["symbol"] == "ABC"
