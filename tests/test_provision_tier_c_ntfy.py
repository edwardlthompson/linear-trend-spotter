"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import json

from scripts import provision_tier_c_ntfy
from utils.notify_provision import build_ntfy_subscribe_url, merge_ntfy_vars
from utils.scan_artifacts import build_notify_public_config, build_public_qualified_snapshot


class _Resp:
    def __init__(self, payload: object | None = None, *, ok: bool = True, status_code: int = 200) -> None:
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = json.dumps(payload or {})

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError(self.text)


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


def test_fetch_env_vars_parses_nested_render_rows() -> None:
    class Session:
        def get(self, *_args, **_kwargs) -> _Resp:
            return _Resp(
                {
                    "envVars": [
                        {"envVar": {"key": "CMC_API_KEY", "value": "secret"}},
                        {"envVar": {"key": "MASKED_SECRET", "value": None}},
                        {"key": "NTFY_ENABLED", "value": "false"},
                    ]
                }
            )

    rows = provision_tier_c_ntfy.fetch_env_vars(Session(), "token", "svc")

    assert rows == [
        {"key": "CMC_API_KEY", "value": "secret"},
        {"key": "MASKED_SECRET", "value": ""},
        {"key": "NTFY_ENABLED", "value": "false"},
    ]


def test_put_ntfy_env_vars_writes_only_per_key_ntfy_updates() -> None:
    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def put(self, url: str, **kwargs) -> _Resp:
            self.calls.append((url, json.loads(kwargs["data"])))
            return _Resp({})

    session = Session()

    provision_tier_c_ntfy.put_ntfy_env_vars(
        session,
        "token",
        "svc",
        {"NTFY_ENABLED": "true", "NTFY_TOPIC": "topic"},
    )

    assert session.calls == [
        (
            "https://api.render.com/v1/services/svc/env-vars/NTFY_ENABLED",
            {"value": "true"},
        ),
        (
            "https://api.render.com/v1/services/svc/env-vars/NTFY_TOPIC",
            {"value": "topic"},
        ),
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
