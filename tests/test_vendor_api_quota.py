"""Vendor quota helpers (CoinGecko / CMC key endpoints)."""

from __future__ import annotations

import logging
from unittest.mock import patch

from utils.scan_costs import build_api_cost_panel_for_snapshot
from utils.vendor_api_quota import fetch_coingecko_key_quota, fetch_cmc_key_quota, fetch_vendor_quotas


def test_fetch_coingecko_quota_success_parses_top_level() -> None:
    log = logging.getLogger("test")
    body = {
        "monthly_call_credit": 500000,
        "current_total_monthly_calls": 1200,
        "current_remaining_monthly_calls": 498800,
        "plan": "analyst",
    }
    with patch("utils.vendor_api_quota.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "{}"
        mock_get.return_value.json.return_value = body
        out = fetch_coingecko_key_quota("CG-pro-key-example", timeout=5.0, logger=log)
    assert out is not None
    assert out["ok"] is True
    assert out["used"] == 1200
    assert out["limit"] == 500000
    assert out["remaining"] == 498800


def test_fetch_cmc_quota_success() -> None:
    log = logging.getLogger("test")
    payload = {
        "status": {"timestamp": "2026-01-01T00:00:00.000Z", "error_code": 0, "credit_count": 0},
        "data": {
            "plan": {"credit_limit_monthly": 10000, "plan_name": "Basic"},
            "usage": {"current_month": {"credits_used": 42, "credits_left": 9958}},
        },
    }
    with patch("utils.vendor_api_quota.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "{}"
        mock_get.return_value.json.return_value = payload
        out = fetch_cmc_key_quota("cmc-key", timeout=5.0, logger=log)
    assert out is not None
    assert out["ok"] is True
    assert out["used"] == 42
    assert out["limit"] == 10000
    assert out["remaining"] == 9958


def test_build_api_cost_panel_merges_vendor_quotas() -> None:
    summary = {"counts": {"coingecko_http_total": 10, "polygon_http_total": 0, "cmc_http_total": 3}}
    vq = {
        "coingecko": {"ok": True, "used": 99, "limit": 1000, "remaining": 901, "source": "test"},
        "coinmarketcap": {"ok": False, "error": "no key"},
    }
    panel = build_api_cost_panel_for_snapshot(summary, vendor_quotas=vq)
    cg = panel["sources"][0]
    assert cg["vendor_quota"]["ok"] is True
    assert cg["vendor_pct_of_monthly_limit"] == 9.9
    cmc = panel["sources"][2]
    assert cmc["vendor_quota"]["ok"] is False


def test_fetch_vendor_quotas_respects_env_off(monkeypatch) -> None:
    monkeypatch.setenv("SCAN_COST_VENDOR_QUOTA_FETCH", "false")
    log = logging.getLogger("test")
    out = fetch_vendor_quotas(coingecko_key="x", cmc_key="y", timeout=1.0, logger=log)
    assert out == {}
