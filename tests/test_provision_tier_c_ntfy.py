"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import json

from scripts import provision_tier_c_ntfy
from utils.notify_provision import build_ntfy_env_vars, build_ntfy_subscribe_url, merge_ntfy_vars
from utils.scan_artifacts import build_notify_public_config, build_public_qualified_snapshot


def test_build_ntfy_subscribe_url() -> None:
    assert build_ntfy_subscribe_url("https://ntfy.sh", "abc") == "https://ntfy.sh/abc"
    assert build_ntfy_subscribe_url("https://ntfy.sh/", "abc") == "https://ntfy.sh/abc"
    assert build_ntfy_subscribe_url("", "") == ""


def test_merge_ntfy_vars_preserves_existing() -> None:
    existing = [{"key": "CMC_API_KEY", "value": "secret"}, {"key": "NTFY_ENABLED", "value": "false"}]
    merged = merge_ntfy_vars(
        existing,
        enabled=True,
        base_url="https://ntfy.sh",
        topic="topic1",
        token="tok1",
        dashboard_url="https://example.com/dash",
    )
    by_key = {e["key"]: e["value"] for e in merged}
    assert by_key["CMC_API_KEY"] == "secret"
    assert by_key["NTFY_ENABLED"] == "true"
    assert by_key["NTFY_TOPIC"] == "topic1"
    assert by_key["NTFY_TOKEN"] == "tok1"
    assert by_key["NTFY_DASHBOARD_URL"] == "https://example.com/dash"


def test_build_ntfy_env_vars_only_returns_managed_keys() -> None:
    updates = build_ntfy_env_vars(
        enabled=True,
        base_url="https://ntfy.sh/",
        topic="topic1",
        token="tok1",
        dashboard_url="https://example.com/dash",
    )
    by_key = {e["key"]: e["value"] for e in updates}
    assert set(by_key) == {
        "NTFY_ENABLED",
        "NTFY_BASE_URL",
        "NTFY_TOPIC",
        "NTFY_TOKEN",
        "NTFY_DASHBOARD_URL",
    }
    assert by_key["NTFY_BASE_URL"] == "https://ntfy.sh"
    assert "CMC_API_KEY" not in by_key


def test_fetch_env_vars_parses_render_nested_envvar_shape() -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "envVars": [
                    {"envVar": {"key": "CMC_API_KEY", "value": None}},
                    {"envVar": {"key": "NTFY_TOPIC", "value": "topic1"}},
                ]
            }

    class _Session:
        def get(self, *args, **kwargs):
            return _Response()

    rows = provision_tier_c_ntfy.fetch_env_vars(_Session(), "token", "svc")
    assert rows == [
        {"key": "CMC_API_KEY", "value": ""},
        {"key": "NTFY_TOPIC", "value": "topic1"},
    ]


def test_put_env_var_writes_single_key_endpoint() -> None:
    calls = []

    class _Response:
        ok = True
        status_code = 200
        text = "ok"

    class _Session:
        def put(self, url, headers, data, timeout):
            calls.append((url, headers, json.loads(data), timeout))
            return _Response()

    provision_tier_c_ntfy.put_env_var(_Session(), "token", "svc", "NTFY_TOPIC", "topic1")
    assert calls == [
        (
            "https://api.render.com/v1/services/svc/env-vars/NTFY_TOPIC",
            {
                "Authorization": "Bearer token",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            {"value": "topic1"},
            120,
        )
    ]


def test_public_snapshot_never_includes_publish_token() -> None:
    cfg = build_notify_public_config(
        ntfy_enabled=True,
        ntfy_base_url="https://ntfy.sh",
        ntfy_topic="t-secret",
    )
    payload = build_public_qualified_snapshot(
        [
            {
                "symbol": "x",
                "name": "X",
                "slug": "x",
                "gains": {"7d": 0.0, "30d": 0.0},
                "uniformity_score": 1.0,
                "health_score": 50,
            }
        ],
        notify_public_config=cfg,
    )
    blob = json.dumps(payload)
    assert "NTFY_TOKEN" not in blob
    assert payload["notify_public_config"]["ntfy_subscribe_url"] == "https://ntfy.sh/t-secret"
