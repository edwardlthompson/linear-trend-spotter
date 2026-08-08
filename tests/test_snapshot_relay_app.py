"""Tests for snapshot_server Flask relay (ingest + public GET)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def relay_client(monkeypatch, tmp_path):
    monkeypatch.setenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "test-secret-xyz")
    monkeypatch.setenv("SNAPSHOT_RELAY_STORE", str(tmp_path / "qualified_public_snapshot.json"))
    for name in list(sys.modules):
        if name == "snapshot_server.app" or name.startswith("snapshot_server.app."):
            del sys.modules[name]
        if name == "snapshot_server":
            del sys.modules[name]
    sys.path.insert(0, str(ROOT))
    from snapshot_server.app import app as flask_app

    return flask_app.test_client()


def test_ingest_then_get(relay_client):
    payload = {"schema_version": 1, "coins": []}
    raw = json.dumps(payload).encode("utf-8")
    h0 = relay_client.get("/relay-health")
    assert h0.status_code == 200
    j0 = json.loads(h0.get_data(as_text=True))
    assert j0.get("has_snapshot_file") is False
    assert j0.get("ingest_auth_configured") is True
    assert j0.get("store_path")
    assert j0.get("last_successful_ingest_at") is None

    bad = relay_client.post(
        "/internal/ingest-snapshot",
        data=raw,
        headers={"Authorization": "Bearer wrong"},
    )
    assert bad.status_code == 401
    h401 = relay_client.get("/relay-health")
    j401 = json.loads(h401.get_data(as_text=True))
    assert j401.get("last_ingest_http_status") == 401
    assert j401.get("last_error") == "unauthorized"

    ok = relay_client.post(
        "/internal/ingest-snapshot",
        data=raw,
        headers={"Authorization": "Bearer test-secret-xyz"},
    )
    assert ok.status_code == 200

    get_r = relay_client.get("/qualified_public_snapshot.json")
    assert get_r.status_code == 200
    assert json.loads(get_r.get_data(as_text=True)) == payload

    h1 = relay_client.get("/relay-health")
    assert h1.status_code == 200
    j1 = json.loads(h1.get_data(as_text=True))
    assert j1.get("has_snapshot_file") is True
    assert j1.get("last_successful_ingest_at")
    assert j1.get("last_successful_ingest_bytes") == len(raw)
    assert j1.get("last_ingest_http_status") == 200
    assert j1.get("last_error") is None


def test_public_serves_backup_if_primary_missing(relay_client, tmp_path, monkeypatch):
    payload = {"schema_version": 1, "coins": [{"symbol": "BTC"}]}
    raw = json.dumps(payload).encode("utf-8")
    store = tmp_path / "qualified_public_snapshot.json"
    backup = tmp_path / "qualified_public_snapshot.json.bak"
    monkeypatch.setenv("SNAPSHOT_RELAY_STORE", str(store))
    monkeypatch.setenv("SNAPSHOT_RELAY_BACKUP_STORE", str(backup))

    ok = relay_client.post(
        "/internal/ingest-snapshot",
        data=raw,
        headers={"Authorization": "Bearer test-secret-xyz"},
    )
    assert ok.status_code == 200
    assert store.exists()
    assert backup.exists()

    # Simulate primary store loss (e.g., transient disk issue); backup should still serve.
    store.unlink()
    get_r = relay_client.get("/qualified_public_snapshot.json")
    assert get_r.status_code == 200
    assert json.loads(get_r.get_data(as_text=True)) == payload


def test_public_fallback_rejects_oversized_response(relay_client, monkeypatch):
    import snapshot_server.app as appmod

    class HugeResponse:
        headers = {"Content-Length": "2048"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, n=-1):
            raise AssertionError("oversized Content-Length should be rejected before read")

    monkeypatch.setenv("SNAPSHOT_RELAY_FALLBACK_URL", "https://example.test/snapshot.json")
    monkeypatch.setenv("SNAPSHOT_MAX_BYTES", "1024")
    monkeypatch.setattr(appmod, "_fallback_last_try_ts", 0.0)
    monkeypatch.setattr(appmod, "urlopen", lambda req, timeout=15: HugeResponse())

    get_r = relay_client.get("/qualified_public_snapshot.json")
    assert get_r.status_code == 503


def test_public_fallback_rejects_stream_larger_than_limit(relay_client, monkeypatch):
    import snapshot_server.app as appmod

    class HugeResponse:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, n=-1):
            return b"{" + (b'"x":' + b'"' + (b"a" * 2048) + b'"}')

    monkeypatch.setenv("SNAPSHOT_RELAY_FALLBACK_URL", "https://example.test/snapshot.json")
    monkeypatch.setenv("SNAPSHOT_MAX_BYTES", "1024")
    monkeypatch.setattr(appmod, "_fallback_last_try_ts", 0.0)
    monkeypatch.setattr(appmod, "urlopen", lambda req, timeout=15: HugeResponse())

    get_r = relay_client.get("/qualified_public_snapshot.json")
    assert get_r.status_code == 503
