"""Public qualified snapshot relay (Milestone Q4+).

Deploy as a Render **Web Service** (see `render.yaml`). The scanner **worker**
cannot serve HTTP; after each scan it **POST**s the JSON here. Browsers on
GitHub Pages **GET** the same file with CORS. Operators may **GET** ``/relay-health``
for last ingest time, HTTP status of the last attempt, and whether the snapshot
file exists (in-memory telemetry; resets on process restart).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from flask import Flask, Response, jsonify, request

app = Flask(__name__)
_logger = logging.getLogger("snapshot_server")
_lock = Lock()

# Operator-facing ingest telemetry (GET /relay-health); not secrets.
_relay_state: dict[str, Any] = {
    "last_successful_ingest_at": None,
    "last_successful_ingest_bytes": None,
    "last_attempt_at": None,
    "last_attempt_status": None,
    "last_error": None,
}


def _utc_now_iso_z() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _ingest_record_success(byte_len: int) -> None:
    now = _utc_now_iso_z()
    with _lock:
        _relay_state["last_successful_ingest_at"] = now
        _relay_state["last_successful_ingest_bytes"] = byte_len
        _relay_state["last_attempt_at"] = now
        _relay_state["last_attempt_status"] = 200
        _relay_state["last_error"] = None


def _ingest_record_failure(status: int, error: str) -> None:
    now = _utc_now_iso_z()
    with _lock:
        _relay_state["last_attempt_at"] = now
        _relay_state["last_attempt_status"] = status
        _relay_state["last_error"] = error[:500] if error else None

_DEFAULT_STORE = "/tmp/qualified_public_snapshot.json"
_DEFAULT_PUBLIC = "qualified_public_snapshot.json"


def _max_bytes() -> int:
    raw = os.getenv("SNAPSHOT_MAX_BYTES", "16777216").strip()
    try:
        return max(1024, int(raw))
    except ValueError:
        return 16777216


app.config["MAX_CONTENT_LENGTH"] = _max_bytes()


def _cors(resp: Response) -> Response:
    origin = os.getenv("SNAPSHOT_RELAY_CORS_ORIGINS", "*").strip() or "*"
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Methods"] = "GET, HEAD, POST, PUT, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


@app.after_request
def _after(resp: Response) -> Response:
    return _cors(resp)


def _store_path() -> Path:
    return Path(os.getenv("SNAPSHOT_RELAY_STORE", _DEFAULT_STORE))


def _public_filename() -> str:
    name = os.getenv("SNAPSHOT_PUBLIC_FILENAME", _DEFAULT_PUBLIC).strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return _DEFAULT_PUBLIC
    return name


def _auth_ingest() -> bool:
    expected = os.getenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "").strip()
    if not expected:
        _logger.warning("QUALIFIED_SNAPSHOT_RELAY_SECRET unset — ingest disabled")
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:].strip()
    return secrets.compare_digest(token, expected)


@app.route("/health", methods=["GET"])
def health() -> tuple[str, int]:
    return "ok", 200


@app.route("/relay-health", methods=["GET", "OPTIONS"])
def relay_health() -> Response | tuple[Response, int]:
    """Small JSON for operators: last ingest time, HTTP status of last attempt, file presence."""
    if request.method == "OPTIONS":
        return Response(status=204)
    path = _store_path()
    with _lock:
        snap = dict(_relay_state)
    has_file = path.is_file()
    secret_set = bool(os.getenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "").strip())
    body: dict[str, Any] = {
        "schema_version": 1,
        "has_snapshot_file": has_file,
        "ingest_auth_configured": secret_set,
        "store_path": str(path),
        "last_successful_ingest_at": snap.get("last_successful_ingest_at"),
        "last_successful_ingest_bytes": snap.get("last_successful_ingest_bytes"),
        "last_ingest_attempt_at": snap.get("last_attempt_at"),
        "last_ingest_http_status": snap.get("last_attempt_status"),
        "last_error": snap.get("last_error"),
    }
    return jsonify(body)


@app.route("/internal/ingest-snapshot", methods=["POST", "PUT", "OPTIONS"])
def ingest() -> tuple[Response, int] | Response:
    if request.method == "OPTIONS":
        return Response(status=204)
    if not _auth_ingest():
        _ingest_record_failure(401, "unauthorized")
        return jsonify({"error": "unauthorized"}), 401
    raw = request.get_data()
    if not raw:
        _ingest_record_failure(400, "empty body")
        return jsonify({"error": "empty body"}), 400
    try:
        json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        _ingest_record_failure(400, f"invalid json: {e}")
        return jsonify({"error": f"invalid json: {e}"}), 400

    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _lock:
        tmp.write_bytes(raw)
        os.replace(tmp, path)
    byte_len = len(raw)
    _ingest_record_success(byte_len)
    _logger.info("snapshot ingested (%s bytes)", byte_len)
    return jsonify({"ok": True, "bytes": byte_len})


def _serve_public() -> Response | tuple[Response, int]:
    path = _store_path()
    if not path.exists():
        return jsonify({"error": "no snapshot yet"}), 503
    with _lock:
        data = path.read_bytes()
    resp = Response(data, mimetype="application/json; charset=utf-8")
    resp.headers["Cache-Control"] = os.getenv(
        "SNAPSHOT_CACHE_CONTROL",
        "public, max-age=60",
    ).strip() or "public, max-age=60"
    return resp


def _register_public() -> None:
    fname = _public_filename()
    rule = f"/{fname}"

    @app.route(rule, methods=["GET", "HEAD", "OPTIONS"])
    def public_snapshot() -> Response | tuple[Response, int]:
        if request.method == "OPTIONS":
            return Response(status=204)
        out = _serve_public()
        if isinstance(out, tuple):
            return out
        if request.method == "HEAD":
            return Response(status=out.status_code, headers=out.headers)
        return out


_register_public()
