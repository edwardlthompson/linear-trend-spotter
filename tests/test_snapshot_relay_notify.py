from __future__ import annotations

import json

from scanner import snapshot_relay_notify


def test_relay_notify_reads_response_with_cap(monkeypatch, tmp_path):
    calls = []

    class HugeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, n=-1):
            calls.append(n)
            return b"x" * (snapshot_relay_notify._RELAY_RESPONSE_MAX_BYTES + 1)

    snapshot_path = tmp_path / "qualified_public_snapshot.json"
    snapshot_path.write_bytes(json.dumps({"schema_version": 1, "coins": []}).encode("utf-8"))

    monkeypatch.setenv("QUALIFIED_SNAPSHOT_RELAY_URL", "https://relay.example.test")
    monkeypatch.setenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "secret")
    monkeypatch.setattr(snapshot_relay_notify, "_RELAY_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(snapshot_relay_notify, "urlopen", lambda req, timeout=120: HugeResponse())

    snapshot_relay_notify.maybe_push_qualified_snapshot_relay(tmp_path, snapshot_path.name)

    assert calls == [snapshot_relay_notify._RELAY_RESPONSE_MAX_BYTES + 1]
