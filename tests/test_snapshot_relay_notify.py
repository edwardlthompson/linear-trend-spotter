"""Scanner-side snapshot relay POST behavior."""

from __future__ import annotations

from urllib.error import URLError

from scanner import snapshot_relay_notify as relay


class _OkResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return b'{"ok":true}'


def test_snapshot_relay_returns_true_when_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("QUALIFIED_SNAPSHOT_RELAY_URL", raising=False)
    monkeypatch.delenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", raising=False)

    assert relay.maybe_push_qualified_snapshot_relay(tmp_path, "missing.json") is True


def test_snapshot_relay_returns_true_after_successful_post(monkeypatch, tmp_path):
    path = tmp_path / "qualified_public_snapshot.json"
    path.write_text('{"schema_version":1,"coins":[]}', encoding="utf-8")
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["body"] = req.data
        seen["timeout"] = timeout
        return _OkResponse()

    monkeypatch.setenv("QUALIFIED_SNAPSHOT_RELAY_URL", "https://snapshot.example.test")
    monkeypatch.setenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "secret")
    monkeypatch.setattr(relay, "urlopen", fake_urlopen)

    assert relay.maybe_push_qualified_snapshot_relay(tmp_path, path.name) is True
    assert seen["url"] == "https://snapshot.example.test/internal/ingest-snapshot"
    assert seen["body"] == b'{"schema_version":1,"coins":[]}'
    assert seen["timeout"] == 120


def test_snapshot_relay_returns_false_after_transport_failures(monkeypatch, tmp_path):
    path = tmp_path / "qualified_public_snapshot.json"
    path.write_text('{"schema_version":1,"coins":[]}', encoding="utf-8")

    def failing_urlopen(req, timeout):
        raise URLError("relay unavailable")

    monkeypatch.setenv("QUALIFIED_SNAPSHOT_RELAY_URL", "https://snapshot.example.test")
    monkeypatch.setenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "secret")
    monkeypatch.setattr(relay, "urlopen", failing_urlopen)
    monkeypatch.setattr(relay.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(relay, "_RELAY_MAX_ATTEMPTS", 2)

    assert relay.maybe_push_qualified_snapshot_relay(tmp_path, path.name) is False
