"""Tests for Tier-B web push copy (qualified entry/exit)."""

from scanner.web_push_notify import (
    _coin_push_row,
    build_qualified_change_push_copy,
    listed_on_for_push,
    maybe_notify_web_push_qualified_changes,
)


def test_build_push_copy_entry_only():
    title, body = build_qualified_change_push_copy(
        entered=[{"symbol": "ada"}, {"symbol": "sol"}],
        exited=[],
    )
    assert "Qualified" in title
    assert "ADA" in body.upper() or "ada" in body.lower()
    assert "SOL" in body.upper() or "sol" in body.lower()
    assert "Out" not in body


def test_build_push_copy_both_sides():
    title, body = build_qualified_change_push_copy(
        entered=[{"symbol": "XRP"}],
        exited=[{"symbol": "doge"}],
    )
    assert "In:" in body
    assert "Out:" in body
    assert "XRP" in body
    assert "DOGE" in body.upper()


def test_build_push_copy_truncates_long_body():
    entered = [{"symbol": f"S{i}"} for i in range(30)]
    _title, body = build_qualified_change_push_copy(entered=entered, exited=[], max_symbols_per_side=5)
    assert len(body) <= 240


def test_listed_on_infer_from_volumes():
    lo = listed_on_for_push(
        {
            "symbol": "X",
            "exchange_volumes": {"coinbase": "N/A", "kraken": "1.2", "mexc": "N/A"},
        }
    )
    assert lo == ["kraken"]


def test_coin_push_row_includes_exit_reason():
    row = _coin_push_row(
        {
            "symbol": "sol",
            "listed_on": ["kraken"],
            "exit_reason": "Uniformity score below threshold (52.1 < 55)",
        }
    )
    assert row is not None
    assert row["symbol"] == "SOL"
    assert row["exit_reason"].startswith("Uniformity score below threshold")


def test_notify_skips_post_when_snapshot_delivery_failed(monkeypatch):
    def fail_if_called(_payload):
        raise AssertionError("push relay should not be called after snapshot delivery failure")

    monkeypatch.setattr("scanner.web_push_notify._post_notify_payload", fail_if_called)

    maybe_notify_web_push_qualified_changes(
        [{"symbol": "ADA", "listed_on": ["kraken"]}],
        [],
        snapshot_delivery_ok=False,
    )
