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


class _Resp:
    def __init__(self, payload, ok: bool = True, status_code: int = 200) -> None:
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, payload=None) -> None:
        self.payload = payload or []
        self.puts = []

    def get(self, *_args, **_kwargs):
        return _Resp(self.payload)

    def put(self, url, *, headers, data, timeout):
        self.puts.append((url, headers, data, timeout))
        return _Resp({})


def test_fetch_env_vars_parses_nested_render_env_rows() -> None:
    session = _Session(
        [
            {"envVar": {"key": "CMC_API_KEY", "value": None}},
            {"envVar": {"key": "NTFY_TOPIC", "value": "topic1"}},
            {"key": "PLAIN_KEY", "value": "plain"},
        ]
    )

    rows = provision.fetch_env_vars(session, "token", "svc")

    assert rows == [
        {"key": "CMC_API_KEY", "value": ""},
        {"key": "NTFY_TOPIC", "value": "topic1"},
        {"key": "PLAIN_KEY", "value": "plain"},
    ]


def test_put_ntfy_env_vars_updates_only_ntfy_keys() -> None:
    session = _Session()

    provision.put_ntfy_env_vars(
        session,
        "token",
        "svc",
        [
            {"key": "CMC_API_KEY", "value": ""},
            {"key": "NTFY_ENABLED", "value": "true"},
            {"key": "NTFY_TOPIC", "value": "topic1"},
        ],
    )

    assert [url for url, _headers, _data, _timeout in session.puts] == [
        f"{provision.API_BASE}/services/svc/env-vars/NTFY_ENABLED",
        f"{provision.API_BASE}/services/svc/env-vars/NTFY_TOPIC",
    ]
    assert [json.loads(data) for _url, _headers, data, _timeout in session.puts] == [
        {"value": "true"},
        {"value": "topic1"},
    ]
