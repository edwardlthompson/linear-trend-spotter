"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from utils.notify_provision import build_ntfy_subscribe_url, merge_ntfy_vars
from utils.scan_artifacts import build_notify_public_config, build_public_qualified_snapshot


def _load_provision_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "provision_tier_c_ntfy.py"
    spec = importlib.util.spec_from_file_location("provision_tier_c_ntfy_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payloads):
        self._payloads = list(payloads)

    def get(self, *_args, **_kwargs):
        return _FakeResponse(self._payloads.pop(0))


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


def test_fetch_env_vars_parses_render_wrapped_rows() -> None:
    provision = _load_provision_script()
    session = _FakeSession(
        [
            {
                "envVars": [
                    {"envVar": {"key": "CMC_API_KEY", "value": "secret"}, "cursor": "row-1"},
                    {"envVar": {"key": "NTFY_ENABLED", "value": "false"}, "cursor": "row-2"},
                ],
            }
        ]
    )

    out = provision.fetch_env_vars(session, "render-token", "srv-1")

    assert out == [
        {"key": "CMC_API_KEY", "value": "secret"},
        {"key": "NTFY_ENABLED", "value": "false"},
    ]


def test_fetch_env_vars_preserves_masked_empty_values() -> None:
    provision = _load_provision_script()
    session = _FakeSession([{"envVars": [{"envVar": {"key": "QUALIFIED_SNAPSHOT_RELAY_SECRET"}}]}])

    out = provision.fetch_env_vars(session, "render-token", "srv-1")

    assert out == [{"key": "QUALIFIED_SNAPSHOT_RELAY_SECRET", "value": ""}]
