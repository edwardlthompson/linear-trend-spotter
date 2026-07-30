"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import json

import pytest

from scripts.provision_tier_c_ntfy import put_ntfy_env_vars
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


def test_merge_ntfy_vars_refuses_masked_non_ntfy_secret() -> None:
    existing = [{"key": "CMC_API_KEY", "value": ""}]
    with pytest.raises(ValueError, match="CMC_API_KEY"):
        merge_ntfy_vars(
            existing,
            enabled=True,
            base_url="https://ntfy.sh",
            topic="topic1",
            token="tok1",
            dashboard_url="",
        )


def test_build_ntfy_env_vars_only_contains_tier_c_keys() -> None:
    updates = build_ntfy_env_vars(
        enabled=True,
        base_url="https://ntfy.sh/",
        topic="topic1",
        token="tok1",
        dashboard_url="https://example.com/dash",
    )
    assert updates == {
        "NTFY_ENABLED": "true",
        "NTFY_BASE_URL": "https://ntfy.sh",
        "NTFY_TOPIC": "topic1",
        "NTFY_TOKEN": "tok1",
        "NTFY_DASHBOARD_URL": "https://example.com/dash",
    }


def test_put_ntfy_env_vars_updates_only_ntfy_keys() -> None:
    class FakeResponse:
        ok = True
        text = ""

    class FakeSession:
        def __init__(self) -> None:
            self.urls: list[str] = []
            self.payloads: list[str] = []

        def put(self, url: str, *, headers: dict[str, str], data: str, timeout: int) -> FakeResponse:
            self.urls.append(url)
            self.payloads.append(data)
            return FakeResponse()

    session = FakeSession()
    put_ntfy_env_vars(
        session,
        "render-token",
        "srv-123",
        {"NTFY_TOPIC": "topic1", "NTFY_TOKEN": "tok1"},
    )

    assert session.urls == [
        "https://api.render.com/v1/services/srv-123/env-vars/NTFY_TOKEN",
        "https://api.render.com/v1/services/srv-123/env-vars/NTFY_TOPIC",
    ]
    assert json.loads(session.payloads[0]) == {"value": "tok1"}
    assert json.loads(session.payloads[1]) == {"value": "topic1"}


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
