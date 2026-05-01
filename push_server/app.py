"""Minimal Tier-B Web Push relay (Milestone Q21).

Deploy as a separate Render **Web Service** (see render.yaml). Stores
PushSubscription JSON on disk (ephemeral unless you mount persistent storage).
No market data in payloads — only short scan-complete text + dashboard URL.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request
from pywebpush import WebPushException, webpush

app = Flask(__name__)
_logger = logging.getLogger("push_server")
_lock = Lock()


def _cors(resp):
    origin = os.getenv("WEB_PUSH_CORS_ORIGINS", "*").strip() or "*"
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


@app.after_request
def _after(resp):
    return _cors(resp)


def _subs_path() -> Path:
    return Path(os.getenv("PUSH_SUBSCRIPTIONS_FILE", "/tmp/push_subscriptions.json"))


def _load_subscriptions() -> list[dict]:
    p = _subs_path()
    if not p.exists():
        return []
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict) and x.get("endpoint")]
    except (OSError, json.JSONDecodeError) as e:
        _logger.warning("load subscriptions: %s", e)
        return []


def _save_subscriptions(subs: list[dict]) -> None:
    p = _subs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=2)
    os.replace(tmp, p)


def _auth_subscribe() -> bool:
    token = os.getenv("WEB_PUSH_SUBSCRIBE_TOKEN", "").strip()
    if not token:
        return True
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return True
    body = request.get_json(silent=True) or {}
    return body.get("token") == token


def _auth_internal() -> bool:
    expected = os.getenv("WEB_PUSH_INTERNAL_SECRET", "").strip()
    if not expected:
        return False
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


def _dedupe_merge(subs: list[dict], new_sub: dict) -> list[dict]:
    ep = new_sub.get("endpoint")
    if not ep:
        return subs
    rest = [s for s in subs if s.get("endpoint") != ep]
    rest.append(new_sub)
    return rest


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/v1/subscribe", methods=["POST", "OPTIONS"])
def subscribe():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _auth_subscribe():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    sub = body.get("subscription")
    if not isinstance(sub, dict) or not sub.get("endpoint"):
        return jsonify({"error": "subscription object required"}), 400
    with _lock:
        subs = _load_subscriptions()
        subs = _dedupe_merge(subs, sub)
        _save_subscriptions(subs)
    return jsonify({"ok": True, "count": len(subs)})


@app.route("/v1/unsubscribe", methods=["POST", "OPTIONS"])
def unsubscribe():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _auth_subscribe():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    endpoint = body.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint.strip():
        return jsonify({"error": "endpoint required"}), 400
    endpoint = endpoint.strip()
    with _lock:
        subs = [s for s in _load_subscriptions() if s.get("endpoint") != endpoint]
        _save_subscriptions(subs)
    return jsonify({"ok": True, "count": len(subs)})


@app.route("/internal/notify-scan", methods=["POST"])
def notify_scan():
    if not _auth_internal():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    title = str(body.get("title") or "Linear Trend Spotter").strip()[:120]
    msg = str(
        body.get("body")
        or "Scan updated — open the qualified dashboard for the latest snapshot.",
    ).strip()[:240]
    url = str(body.get("url") or "").strip()[:2000]

    vapid_private = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    vapid_email = os.getenv("VAPID_CONTACT_EMAIL", "").strip()
    if not vapid_private or not vapid_email:
        return jsonify({"error": "VAPID keys not configured on push service"}), 503

    payload = json.dumps({"title": title, "body": msg, "url": url}, separators=(",", ":"))

    with _lock:
        subs = _load_subscriptions()
    if not subs:
        return jsonify({"sent": 0, "failed": 0, "removed": 0, "message": "no subscriptions"})

    sent = 0
    failed = 0
    removed = 0
    kept: list[dict] = []

    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": f"mailto:{vapid_email}"},
                ttl=86400,
            )
            sent += 1
            kept.append(sub)
        except WebPushException as e:
            status = getattr(e.response, "status_code", None) if e.response else None
            if status in (404, 410):
                removed += 1
                continue
            _logger.warning("webpush failed: %s", e)
            failed += 1
            kept.append(sub)
        except Exception as e:
            _logger.warning("webpush error: %s", e)
            failed += 1
            kept.append(sub)

    with _lock:
        _save_subscriptions(kept)

    return jsonify({"sent": sent, "failed": failed, "removed": removed})
