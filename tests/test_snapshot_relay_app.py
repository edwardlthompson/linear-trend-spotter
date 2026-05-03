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
