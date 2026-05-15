"""Push relay app correctness tests."""

from __future__ import annotations

import json

import push_server.app as push_app


def _read_subscriptions(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_notify_scan_preserves_subscription_added_during_push(tmp_path, monkeypatch):
    subs_path = tmp_path / "subs.json"
    monkeypatch.setenv("PUSH_SUBSCRIPTIONS_FILE", str(subs_path))
    monkeypatch.setenv("WEB_PUSH_INTERNAL_SECRET", "secret")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-key")
    monkeypatch.setenv("VAPID_CONTACT_EMAIL", "ops@example.com")

    original = {"subscription": {"endpoint": "https://push.example/old"}, "notify_exchanges": []}
    added = {"subscription": {"endpoint": "https://push.example/new"}, "notify_exchanges": []}
    push_app._save_subscriptions([original])

    def fake_webpush(**_kwargs):
        with push_app._lock:
            subs = push_app._load_subscriptions()
            push_app._save_subscriptions(push_app._dedupe_merge_envelope(subs, added))

    monkeypatch.setattr(push_app, "webpush", fake_webpush)

    resp = push_app.app.test_client().post(
        "/internal/notify-scan",
        headers={"Authorization": "Bearer secret"},
        json={"entered_coins": [{"symbol": "ADA", "listed_on": []}], "exited_coins": []},
    )

    assert resp.status_code == 200
    endpoints = {env["subscription"]["endpoint"] for env in _read_subscriptions(subs_path)}
    assert endpoints == {"https://push.example/old", "https://push.example/new"}


def test_notify_scan_removes_expired_endpoint_without_dropping_concurrent_add(tmp_path, monkeypatch):
    subs_path = tmp_path / "subs.json"
    monkeypatch.setenv("PUSH_SUBSCRIPTIONS_FILE", str(subs_path))
    monkeypatch.setenv("WEB_PUSH_INTERNAL_SECRET", "secret")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-key")
    monkeypatch.setenv("VAPID_CONTACT_EMAIL", "ops@example.com")

    expired = {"subscription": {"endpoint": "https://push.example/expired"}, "notify_exchanges": []}
    added = {"subscription": {"endpoint": "https://push.example/new"}, "notify_exchanges": []}
    push_app._save_subscriptions([expired])

    class GoneResponse:
        status_code = 410

    def fake_webpush(**_kwargs):
        with push_app._lock:
            subs = push_app._load_subscriptions()
            push_app._save_subscriptions(push_app._dedupe_merge_envelope(subs, added))
        raise push_app.WebPushException("gone", response=GoneResponse())

    monkeypatch.setattr(push_app, "webpush", fake_webpush)

    resp = push_app.app.test_client().post(
        "/internal/notify-scan",
        headers={"Authorization": "Bearer secret"},
        json={"entered_coins": [{"symbol": "ADA", "listed_on": []}], "exited_coins": []},
    )

    assert resp.status_code == 200
    assert resp.get_json()["removed"] == 1
    endpoints = {env["subscription"]["endpoint"] for env in _read_subscriptions(subs_path)}
    assert endpoints == {"https://push.example/new"}
