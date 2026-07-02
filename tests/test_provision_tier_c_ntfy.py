"""Tests for Tier-C ntfy provisioning helpers."""

from __future__ import annotations

import json

from scripts.provision_tier_c_ntfy import fetch_env_vars
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


def test_fetch_env_vars_unwraps_render_envvar_rows_and_cursor() -> None:
    class Response:
        def __init__(self, payload: object) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return self._payload

    class Session:
        def __init__(self) -> None:
            self.params: list[dict[str, object]] = []

        def get(self, *_args: object, params: dict[str, object], **_kwargs: object) -> Response:
            self.params.append(dict(params))
            if len(self.params) == 1:
                return Response(
                    [
                        {"envVar": {"key": "CMC_API_KEY", "value": "secret"}, "cursor": "next-page"},
                    ]
                )
            return Response(
                [
                    {"envVar": {"key": "NTFY_ENABLED", "value": "false"}},
                    {"key": "TOP_LEVEL", "value": "ok"},
                ]
            )

    session = Session()

    env_vars = fetch_env_vars(session, "render-token", "service-id")

    assert env_vars == [
        {"key": "CMC_API_KEY", "value": "secret"},
        {"key": "NTFY_ENABLED", "value": "false"},
        {"key": "TOP_LEVEL", "value": "ok"},
    ]
    assert session.params == [{"limit": 100}, {"limit": 100, "cursor": "next-page"}]
