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


class _FakeResponse:
    def __init__(self, body, ok: bool = True, status_code: int = 200) -> None:
        self._body = body
        self.ok = ok
        self.status_code = status_code
        self.text = json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self) -> None:
        if not self.ok:
            raise AssertionError(f"unexpected HTTP {self.status_code}")


class _EnvSession:
    def __init__(self, pages) -> None:
        self.pages = list(pages)
        self.puts: list[tuple[str, str]] = []

    def get(self, *args, **kwargs):
        return _FakeResponse(self.pages.pop(0))

    def put(self, url, headers=None, data=None, timeout=None):
        self.puts.append((url, data))
        return _FakeResponse({"ok": True})


def test_fetch_env_vars_accepts_render_nested_envvar_rows() -> None:
    session = _EnvSession(
        [
            [
                {"envVar": {"key": "CMC_API_KEY", "value": "secret"}, "cursor": "next"},
            ],
            [
                {"envVar": {"key": "NTFY_ENABLED", "value": "false"}},
            ],
        ]
    )

    env = provision.fetch_env_vars(session, "render-token", "srv-test")

    assert env == [
        {"key": "CMC_API_KEY", "value": "secret"},
        {"key": "NTFY_ENABLED", "value": "false"},
    ]


def test_put_ntfy_vars_updates_individual_keys_only() -> None:
    session = _EnvSession([])

    provision.put_ntfy_vars(
        session,
        "render-token",
        "srv-test",
        {"NTFY_ENABLED": "true", "NTFY_TOPIC": "topic1"},
    )

    assert [url for url, _data in session.puts] == [
        "https://api.render.com/v1/services/srv-test/env-vars/NTFY_ENABLED",
        "https://api.render.com/v1/services/srv-test/env-vars/NTFY_TOPIC",
    ]
    assert [json.loads(data) for _url, data in session.puts] == [
        {"value": "true"},
        {"value": "topic1"},
    ]
