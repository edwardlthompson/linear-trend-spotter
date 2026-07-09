"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import json

from scripts import provision_tier_c_ntfy as provision
from utils.notify_provision import build_ntfy_env_updates, build_ntfy_subscribe_url, merge_ntfy_vars
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


def test_build_ntfy_env_updates_contains_only_owned_keys() -> None:
    updates = build_ntfy_env_updates(
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


def test_fetch_env_vars_parses_nested_render_env_rows() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "envVars": [
                    {"envVar": {"key": "CMC_API_KEY", "value": "secret"}},
                    {"key": "NTFY_ENABLED", "value": "true"},
                    {"envVar": {"key": "MASKED_SECRET", "value": None}},
                ]
            }

    class FakeSession:
        def get(self, *args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse()

    env = provision.fetch_env_vars(FakeSession(), "render-token", "svc-id")

    assert env == [
        {"key": "CMC_API_KEY", "value": "secret"},
        {"key": "NTFY_ENABLED", "value": "true"},
        {"key": "MASKED_SECRET", "value": ""},
    ]


def test_put_ntfy_env_vars_updates_only_passed_keys() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class FakeResponse:
        ok = True
        status_code = 200
        text = "{}"

    class FakeSession:
        def put(self, url: str, *, data: str, **kwargs: object) -> FakeResponse:
            calls.append((url, json.loads(data)))
            return FakeResponse()

    provision.put_ntfy_env_vars(
        FakeSession(),
        "render-token",
        "svc-id",
        {
            "NTFY_ENABLED": "true",
            "NTFY_TOPIC": "topic1",
            "NTFY_TOKEN": "tok1",
        },
    )

    assert calls == [
        ("https://api.render.com/v1/services/svc-id/env-vars/NTFY_ENABLED", {"value": "true"}),
        ("https://api.render.com/v1/services/svc-id/env-vars/NTFY_TOKEN", {"value": "tok1"}),
        ("https://api.render.com/v1/services/svc-id/env-vars/NTFY_TOPIC", {"value": "topic1"}),
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
