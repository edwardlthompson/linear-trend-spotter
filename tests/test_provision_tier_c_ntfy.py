"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import json

from scripts import provision_tier_c_ntfy as provision
from utils.notify_provision import build_ntfy_subscribe_url, merge_ntfy_vars
from utils.scan_artifacts import build_notify_public_config, build_public_qualified_snapshot


class _FakeResponse:
    def __init__(self, payload=None, *, ok: bool = True, status_code: int = 200, text: str = "ok") -> None:
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError(self.text)


class _FakeSession:
    def __init__(self, get_payload=None) -> None:
        self.get_payload = get_payload
        self.put_calls: list[dict[str, object]] = []

    def get(self, *args, **kwargs):
        return _FakeResponse(self.get_payload)

    def put(self, url, **kwargs):
        self.put_calls.append({"url": url, **kwargs})
        return _FakeResponse()


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


def test_fetch_env_vars_accepts_nested_render_rows() -> None:
    session = _FakeSession(
        {
            "envVars": [
                {"envVar": {"key": "CMC_API_KEY", "value": "masked-secret"}},
                {"envVar": {"key": "NTFY_ENABLED", "value": "false"}},
                {"key": "PLAIN_SHAPE", "value": "ok"},
            ]
        }
    )

    rows = provision.fetch_env_vars(session, "render-token", "srv-test")

    assert rows == [
        {"key": "CMC_API_KEY", "value": "masked-secret"},
        {"key": "NTFY_ENABLED", "value": "false"},
        {"key": "PLAIN_SHAPE", "value": "ok"},
    ]


def test_put_ntfy_env_vars_updates_only_ntfy_keys_per_key() -> None:
    session = _FakeSession()

    provision.put_ntfy_env_vars(
        session,
        "render-token",
        "srv-test",
        [
            {"key": "NTFY_ENABLED", "value": "true"},
            {"key": "NTFY_TOPIC", "value": "topic"},
        ],
    )

    assert [call["url"] for call in session.put_calls] == [
        "https://api.render.com/v1/services/srv-test/env-vars/NTFY_ENABLED",
        "https://api.render.com/v1/services/srv-test/env-vars/NTFY_TOPIC",
    ]
    assert [json.loads(str(call["data"])) for call in session.put_calls] == [
        {"value": "true"},
        {"value": "topic"},
    ]


def test_put_ntfy_env_vars_rejects_non_ntfy_key() -> None:
    session = _FakeSession()

    try:
        provision.put_ntfy_env_vars(
            session,
            "render-token",
            "srv-test",
            [{"key": "CMC_API_KEY", "value": "do-not-write"}],
        )
    except SystemExit as exc:
        assert "non-NTFY env var" in str(exc)
    else:
        raise AssertionError("expected non-NTFY env var write to abort")
    assert session.put_calls == []


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
