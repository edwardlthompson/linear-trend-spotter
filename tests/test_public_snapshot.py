"""Public qualified snapshot payload shape."""

from __future__ import annotations

import json

from utils.scan_artifacts import build_public_qualified_snapshot
from utils.scan_costs import build_api_cost_panel_for_snapshot


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
    assert "snapshot_validation" in payload
    assert payload["snapshot_validation"].get("level") in ("ok", "warn", "error")
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


def test_api_cost_panel_optional_top_level() -> None:
    summary = {
        "counts": {
            "coingecko_http_total": 40,
            "coingecko_http_markets": 30,
            "coingecko_http_ohlc": 10,
            "polygon_http_total": 5,
            "polygon_http_aggs": 4,
            "polygon_http_other": 1,
            "cmc_http_total": 12,
            "cmc_http_listings": 2,
            "cmc_http_ohlcv": 10,
        },
    }
    panel = build_api_cost_panel_for_snapshot(
        summary,
        coingecko_monthly_http_cap=10_000,
        polygon_monthly_http_cap=0,
        cmc_monthly_http_cap=50_000,
    )
    payload = build_public_qualified_snapshot(
        [],
        field_set="full",
        scan_interval_seconds=3600,
        api_cost_panel=panel,
    )
    assert payload["api_cost_panel"]["sources"][0]["id"] == "coingecko"
    assert payload["api_cost_panel"]["sources"][0]["this_scan_http"] == 40
    assert payload["api_cost_panel"]["sources"][0]["pct_of_monthly_budget"] == 0.4
    assert payload["api_cost_panel"]["sources"][2]["this_scan_http"] == 12
    assert payload["api_cost_panel"]["sources"][2]["pct_of_monthly_budget"] is not None


def test_regime_gate_optional_top_level() -> None:
    regime = {
        "enabled": True,
        "passed": False,
        "blocked": True,
        "reason": "btc_30d_below_min (-1.00 < 0.00)",
        "btc_7d_pct": 2.5,
        "btc_30d_pct": -1.0,
        "btc_min_30d_gain_pct": 0.0,
        "btc_max_abs_7d_gain_pct": 25.0,
    }
    payload = build_public_qualified_snapshot(
        [],
        field_set="full",
        scan_interval_seconds=3600,
        regime_gate=regime,
    )
    assert payload["coins"] == []
    assert payload["regime_gate"] == regime


def test_full_includes_closes_30d_when_numeric_series() -> None:
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 1.0,
            "health_score": 50,
            "closes_30d": [100.0, 101.0, 99.5],
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=3600)
    assert payload["coins"][0].get("closes_30d") == [100.0, 101.0, 99.5]


def test_full_includes_closes_1h_when_numeric_series() -> None:
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 1.0,
            "health_score": 50,
            "closes_1h": [1.0, 1.01, 1.02, 1.0],
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=3600)
    assert payload["coins"][0].get("closes_1h") == [1.0, 1.01, 1.02, 1.0]


def test_full_closes_1h_keeps_tail_up_to_720_hourly_bars() -> None:
    """Public JSON must not cap hourly closes at 200 (breaks 7d vs 30d sparklines on dashboard)."""
    long = [float(i) for i in range(800)]
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 1.0,
            "health_score": 50,
            "closes_1h": long,
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=3600)
    out = payload["coins"][0].get("closes_1h")
    assert out == [float(i) for i in range(80, 800)]


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


def test_qualification_exits_optional_top_level() -> None:
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
    exited = [{"symbol": "xrp", "exit_reason": "7d gain below threshold (1.0% < 2%)"}]
    payload = build_public_qualified_snapshot(
        rows,
        field_set="full",
        scan_interval_seconds=3600,
        qualification_exits=exited,
    )
    assert payload["coins"][0]["symbol"] == "ADA"
    assert payload["qualification_exits"] == [
        {"symbol": "XRP", "exit_reason": "7d gain below threshold (1.0% < 2%)"},
    ]


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


def test_notify_public_config_included_when_set() -> None:
    from utils.scan_artifacts import build_notify_public_config

    cfg = build_notify_public_config(
        ntfy_enabled=True,
        ntfy_base_url="https://ntfy.sh",
        ntfy_topic="secret-topic-abc",
    )
    assert cfg == {"ntfy_subscribe_url": "https://ntfy.sh/secret-topic-abc"}
    rows = [
        {
            "symbol": "btc",
            "name": "Bitcoin",
            "slug": "bitcoin",
            "gains": {"7d": 1.0, "30d": 2.0},
            "uniformity_score": 50.0,
            "health_score": 60,
        },
    ]
    payload = build_public_qualified_snapshot(
        rows,
        field_set="full",
        scan_interval_seconds=3600,
        notify_public_config=cfg,
    )
    assert payload["notify_public_config"]["ntfy_subscribe_url"] == "https://ntfy.sh/secret-topic-abc"
    assert "NTFY_TOKEN" not in json.dumps(payload)


def test_notify_public_config_uses_ntfy_environment(monkeypatch, tmp_path) -> None:
    from config.settings import Settings
    from utils.scan_artifacts import build_notify_public_config

    monkeypatch.setenv("NTFY_ENABLED", "1")
    monkeypatch.setenv("NTFY_BASE_URL", "https://ntfy.example/")
    monkeypatch.setenv("NTFY_TOPIC", "env-topic")
    monkeypatch.setenv("NTFY_TOKEN", "publish-token")
    s = Settings(config_path=str(tmp_path / "missing.json"))

    cfg = build_notify_public_config(
        ntfy_enabled=s.ntfy_enabled,
        ntfy_base_url=s.ntfy_base_url,
        ntfy_topic=s.ntfy_topic,
    )

    assert cfg == {"ntfy_subscribe_url": "https://ntfy.example/env-topic"}
    assert "publish-token" not in json.dumps(cfg)


def test_notify_public_config_omitted_when_disabled() -> None:
    from utils.scan_artifacts import build_notify_public_config

    assert build_notify_public_config(ntfy_enabled=False, ntfy_topic="x") is None
    rows = [
        {
            "symbol": "btc",
            "name": "Bitcoin",
            "slug": "bitcoin",
            "gains": {"7d": 1.0, "30d": 2.0},
            "uniformity_score": 50.0,
            "health_score": 60,
        },
    ]
    payload = build_public_qualified_snapshot(rows, field_set="full", scan_interval_seconds=3600)
    assert "notify_public_config" not in payload
