"""Regression tests for healthy zero-qualified scanner branches."""

from __future__ import annotations

from types import SimpleNamespace

import main


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ActiveDb:
    def __init__(self) -> None:
        self.current_rows = None
        self.kwargs = None
        self.registered: list[tuple[str, str, int]] = []

    def get_entered_exited(self, current_rows, **kwargs):
        self.current_rows = current_rows
        self.kwargs = kwargs
        exited = [
            {
                "symbol": "OLD",
                "name": "Old Coin",
                "slug": "old-coin",
                "listed_on": ["kraken"],
            }
        ]
        return [], exited, []

    def register_exit(self, symbol: str, reason: str = "", cooldown_hours: int = 0) -> None:
        self.registered.append((symbol, reason, cooldown_hours))


def _configure_zero_scan(monkeypatch, *, gain_rows: list[dict], cg_rows: list[dict]):
    active_db = _ActiveDb()
    cache = _Closable()
    tv_mapper = _Closable()
    exchange_db = _Closable()
    cg_mapper = _Closable()
    snapshots: list[dict] = []
    web_push: list[tuple[list, list]] = []
    ntfy_push: list[tuple[list, list]] = []

    monkeypatch.setitem(main.settings._config, "ARTIFACT_HYGIENE_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_ENABLED", True)
    monkeypatch.setitem(main.settings._config, "PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET", "minimal")
    monkeypatch.setitem(main.settings._config, "SCAN_HEARTBEAT_ENABLED", False)
    monkeypatch.setitem(main.settings._config, "NTFY_ENABLED", False)
    monkeypatch.setattr(
        main,
        "initialize_runtime_components",
        lambda _settings: {
            "history_db": object(),
            "active_db": active_db,
            "cache": cache,
            "exchange_db": exchange_db,
            "tv_mapper": tv_mapper,
            "cmc": object(),
            "gecko": object(),
            "history_fallback": object(),
            "cg_mapper": cg_mapper,
            "cmc_slug_resolver": None,
        },
    )
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
    monkeypatch.setattr(main, "load_exchange_symbol_universe", lambda *_args, **_kwargs: (["AAA"], {"AAA"}))
    monkeypatch.setattr(main, "prefetch_alias_markets_by_gecko_id", lambda **_kwargs: {})
    monkeypatch.setattr(main, "top_up_alias_markets_for_symbols", lambda **_kwargs: None)
    monkeypatch.setattr(main, "apply_gain_volume_filter", lambda *args, **kwargs: gain_rows)
    monkeypatch.setattr(main, "attach_target_exchange_listings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "attach_coin_gecko_ids_and_learn", lambda *_args, **_kwargs: (cg_rows, []))
    monkeypatch.setattr(
        main,
        "write_public_qualified_snapshot",
        lambda _data_dir, _filename, final_results, **kwargs: snapshots.append(
            {"final_results": final_results, **kwargs}
        ),
    )
    monkeypatch.setattr(main, "maybe_push_qualified_snapshot_relay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main,
        "maybe_notify_web_push_qualified_changes",
        lambda entered, exited: web_push.append((entered, exited)),
    )
    monkeypatch.setattr(
        main,
        "maybe_notify_ntfy_qualified_changes",
        lambda entered, exited: ntfy_push.append((entered, exited)),
    )

    return SimpleNamespace(
        active_db=active_db,
        cache=cache,
        tv_mapper=tv_mapper,
        exchange_db=exchange_db,
        cg_mapper=cg_mapper,
        snapshots=snapshots,
        web_push=web_push,
        ntfy_push=ntfy_push,
    )


def test_no_gain_qualified_scan_finalizes_exits_and_snapshot(monkeypatch) -> None:
    state = _configure_zero_scan(monkeypatch, gain_rows=[], cg_rows=[])

    main.run_scanner()

    assert state.active_db.current_rows == []
    assert state.snapshots[0]["final_results"] == []
    assert state.snapshots[0]["qualification_exits"][0]["symbol"] == "OLD"
    assert state.snapshots[0]["qualification_exits"][0]["exit_reason"] == "No longer listed on target exchanges"
    assert state.web_push[0][1][0]["symbol"] == "OLD"
    assert state.ntfy_push[0][1][0]["symbol"] == "OLD"
    assert state.cache.closed is True


def test_no_coingecko_id_scan_finalizes_exits_and_snapshot(monkeypatch) -> None:
    state = _configure_zero_scan(monkeypatch, gain_rows=[{"symbol": "AAA"}], cg_rows=[])

    main.run_scanner()

    assert state.active_db.current_rows == []
    assert state.snapshots[0]["final_results"] == []
    assert state.snapshots[0]["qualification_exits"][0]["symbol"] == "OLD"
    assert state.web_push[0][1][0]["symbol"] == "OLD"
    assert state.ntfy_push[0][1][0]["symbol"] == "OLD"
    assert state.cg_mapper.closed is True
