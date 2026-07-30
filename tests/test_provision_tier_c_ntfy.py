"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import json

from scripts import provision_tier_c_ntfy as provision
from utils.notify_provision import build_ntfy_subscribe_url, merge_ntfy_vars
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


def test_fetch_env_vars_normalizes_nested_render_rows() -> None:
    class Resp:
        ok = True
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {"envVar": {"key": "CMC_API_KEY", "value": None}},
                {"envVar": {"key": "NTFY_TOPIC", "value": "topic"}},
            ]

    class Session:
        def get(self, *args, **kwargs):
            return Resp()

    assert provision.fetch_env_vars(Session(), "token", "svc") == [
        {"key": "CMC_API_KEY", "value": ""},
        {"key": "NTFY_TOPIC", "value": "topic"},
    ]


def test_put_ntfy_env_vars_updates_only_ntfy_keys() -> None:
    class Resp:
        ok = True
        text = ""

    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def put(self, url, *, headers, data, timeout):
            self.calls.append((url, data))
            return Resp()

    session = Session()
    provision.put_ntfy_env_vars(
        session,
        "token",
        "svc",
        [
            {"key": "CMC_API_KEY", "value": ""},
            {"key": "NTFY_ENABLED", "value": "true"},
            {"key": "NTFY_TOKEN", "value": "secret"},
        ],
    )

    assert [url.rsplit("/", 1)[-1] for url, _ in session.calls] == ["NTFY_ENABLED", "NTFY_TOKEN"]
    assert json.loads(session.calls[0][1]) == {"value": "true"}
