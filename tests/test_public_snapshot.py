"""Public qualified snapshot payload shape."""

from __future__ import annotations

from utils.scan_artifacts import build_public_qualified_snapshot


def test_full_field_set_includes_scan_interval_and_backtest() -> None:
    rows = [
        {
            "symbol": "ada",
            "name": "Cardano",
            "slug": "cardano",
            "gains": {"7d": 1.0, "30d": 2.0},
            "uniformity_score": 50.0,
            "health_score": 60,
            "backtest_top_strategies": [{"rank": 1}],
            "backtest_buy_hold": {"return_pct": 1.2},
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=1800)
    assert payload["scan_interval_seconds"] == 1800
    assert payload["coins"][0]["backtest_top_strategies"] == [{"rank": 1}]
    assert payload["coins"][0]["backtest_buy_hold"] == {"return_pct": 1.2}


def test_full_includes_https_chart_image_url_only() -> None:
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 1.0,
            "health_score": 50,
            "chart_image_url": "https://example.com/c.png",
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=3600)
    assert payload["coins"][0].get("chart_image_url") == "https://example.com/c.png"


def test_full_strips_non_https_chart_url() -> None:
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 1.0,
            "health_score": 50,
            "chart_image_url": "http://insecure.example/x.png",
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=3600)
    assert "chart_image_url" not in payload["coins"][0]


def test_scan_health_fields_optional() -> None:
    rows = [
        {
            "symbol": "ada",
            "name": "Cardano",
            "slug": "cardano",
            "gains": {"7d": 1.0, "30d": 2.0},
            "uniformity_score": 50.0,
            "health_score": 60,
        },
    ]
    health = {"scan_duration_s": 123.456, "coins_evaluated": 4000, "errors_count": 2}
    payload = build_public_qualified_snapshot(
        rows,
        field_set="minimal",
        scan_interval_seconds=3600,
        scan_health=health,
    )
    assert payload["scan_duration_s"] == 123.46
    assert payload["coins_evaluated"] == 4000
    assert payload["errors_count"] == 2


def test_scan_health_omits_invalid_values() -> None:
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 1.0,
            "health_score": 1,
        },
    ]
    payload = build_public_qualified_snapshot(
        rows,
        field_set="minimal",
        scan_health={"scan_duration_s": float("nan"), "coins_evaluated": -1, "errors_count": "x"},
    )
    assert "scan_duration_s" not in payload
    assert "coins_evaluated" not in payload
    assert "errors_count" not in payload


def test_full_includes_listed_on_and_volume_acceleration() -> None:
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 3.0, "30d": 10.0},
            "uniformity_score": 70.0,
            "health_score": 80,
            "listed_on": ["binance", "kraken"],
            "volume_acceleration_pct": 12.5,
            "volume_acceleration_window_days": 14,
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=3600)
    coin = payload["coins"][0]
    assert coin["listed_on"] == ["binance", "kraken"]
    assert coin["volume_acceleration_pct"] == 12.5
    assert coin["volume_acceleration_window_days"] == 14


def test_minimal_field_set_omits_backtest_and_exchange_fields() -> None:
    rows = [
        {
            "symbol": "ada",
            "name": "Cardano",
            "slug": "cardano",
            "gains": {"7d": 1.0, "30d": 2.0},
            "uniformity_score": 50.0,
            "health_score": 60,
            "backtest_top_strategies": [{"rank": 1}],
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="minimal", scan_interval_seconds=3600)
    coin = payload["coins"][0]
    assert "backtest_top_strategies" not in coin
    assert "exchange_volumes" not in coin
    assert "listed_on" not in coin
    assert "volume_acceleration_pct" not in coin
