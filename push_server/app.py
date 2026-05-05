"""Minimal Tier-B Web Push relay (Milestone Q21).

Deploy as a separate Render **Web Service** (see render.yaml). Stores
PushSubscription JSON on disk (ephemeral unless you mount persistent storage).
No market OHLCV in payloads — short text + dashboard URL. The scanner POSTs when
the qualified **active** list gains or loses members; each subscription may
include ``notify_exchanges`` so pushes match the same exchange filter semantics
as the dashboard (Kraken-only subscribers skip MEXC-only listings).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path
from threading import Lock
from typing import Any

from flask import Flask, jsonify, request
from pywebpush import WebPushException, webpush

try:
    # Works when imported as package from repo root.
    from push_server.notify_filtering import (
        filter_events_for_subscriber,
        normalize_notify_exchange_ids,
    )
except ModuleNotFoundError:
    # Works when Render uses rootDir=push_server and imports app:app.
    from notify_filtering import (  # type: ignore[no-redef]
        filter_events_for_subscriber,
        normalize_notify_exchange_ids,
    )

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


def _normalize_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    """Wrap legacy flat PushSubscription dicts as {subscription, notify_exchanges}."""
    if "subscription" in raw and isinstance(raw.get("subscription"), dict):
        sub = raw["subscription"]
        ne = normalize_notify_exchange_ids(raw.get("notify_exchanges"))
        return {"subscription": sub, "notify_exchanges": ne}
    if raw.get("endpoint"):
        inner = {k: raw[k] for k in raw if k in ("endpoint", "keys", "expirationTime")}
        ne = normalize_notify_exchange_ids(raw.get("notify_exchanges"))
        return {"subscription": inner, "notify_exchanges": ne}
    return raw


def _load_subscriptions() -> list[dict[str, Any]]:
    p = _subs_path()
    if not p.exists():
        return []
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        out: list[dict[str, Any]] = []
        for x in data:
            if isinstance(x, dict) and x.get("endpoint"):
                out.append(_normalize_envelope(x))
            elif isinstance(x, dict) and isinstance(x.get("subscription"), dict) and x["subscription"].get("endpoint"):
                out.append(_normalize_envelope(x))
        return out
    except (OSError, json.JSONDecodeError) as e:
        _logger.warning("load subscriptions: %s", e)
        return []


def _save_subscriptions(subs: list[dict[str, Any]]) -> None:
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


def _envelope_endpoint(env: dict[str, Any]) -> str | None:
    sub = env.get("subscription")
    if isinstance(sub, dict):
        return str(sub.get("endpoint") or "").strip() or None
    return None


def _trim(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def _entry_notification_payload(coin: dict[str, Any], url: str) -> dict[str, str]:
    sym = str(coin.get("symbol", "")).upper().strip() or "UNKNOWN"
    # Unique tag per push so clients do not collapse multiple events (see docs/dashboard/sw.js).
    tag = f"q-ent-{sym.lower()}-{secrets.token_hex(4)}"
    return {
        "title": _trim(f"Qualified entry: {sym}", 120),
        "body": _trim(f"{sym} entered the qualified list.", 240),
        "url": _trim(url, 2000),
        "tag": _trim(tag, 64),
    }


def _exit_notification_payload(coin: dict[str, Any], url: str) -> dict[str, str]:
    sym = str(coin.get("symbol", "")).upper().strip() or "UNKNOWN"
    reason = str(coin.get("exit_reason", "")).strip()
    if reason:
        body = f"{sym} exited the qualified list. Reason: {reason}"
    else:
        body = f"{sym} exited the qualified list."
    tag = f"q-ext-{sym.lower()}-{secrets.token_hex(4)}"
    return {
        "title": _trim(f"Qualified exit: {sym}", 120),
        "body": _trim(body, 240),
        "url": _trim(url, 2000),
        "tag": _trim(tag, 64),
    }


def _dedupe_merge_envelope(subs: list[dict[str, Any]], new_env: dict[str, Any]) -> list[dict[str, Any]]:
    ep = _envelope_endpoint(new_env)
    if not ep:
        return subs
    rest = [s for s in subs if _envelope_endpoint(s) != ep]
    rest.append(new_env)
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
    notify_ids = normalize_notify_exchange_ids(body.get("notify_exchanges"))
    envelope = {"subscription": sub, "notify_exchanges": notify_ids}
    with _lock:
        subs = _load_subscriptions()
        subs = _dedupe_merge_envelope(subs, envelope)
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
        subs = [s for s in _load_subscriptions() if _envelope_endpoint(s) != endpoint]
        _save_subscriptions(subs)
    return jsonify({"ok": True, "count": len(subs)})


@app.route("/internal/notify-scan", methods=["POST"])
def notify_scan():
    if not _auth_internal():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    title_default = str(body.get("title") or "Qualified list changed").strip()[:120]
    msg_default = str(
        body.get("body")
        or "Open the qualified dashboard for the latest snapshot.",
    ).strip()[:240]
    url = str(body.get("url") or "").strip()[:2000]

    entered_coins: list[dict[str, Any]] = []
    exited_coins: list[dict[str, Any]] = []
    ec = body.get("entered_coins")
    if isinstance(ec, list):
        entered_coins = [x for x in ec if isinstance(x, dict)]
    xc = body.get("exited_coins")
    if isinstance(xc, list):
        exited_coins = [x for x in xc if isinstance(x, dict)]

    # Scanner always POSTs entered_coins/exited_coins. Never downgrade to one batched notification
    # when those keys exist but lists are empty (would hide per-coin UX).
    per_coin_api = "entered_coins" in body or "exited_coins" in body

    vapid_private = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    vapid_email = os.getenv("VAPID_CONTACT_EMAIL", "").strip()
    if not vapid_private or not vapid_email:
        return jsonify({"error": "VAPID keys not configured on push service"}), 503

    with _lock:
        subs = _load_subscriptions()
    if not subs:
        return jsonify({"sent": 0, "failed": 0, "removed": 0, "message": "no subscriptions"})

    sent = 0
    failed = 0
    removed = 0
    kept: list[dict[str, Any]] = []

    for env in subs:
        sub_info = env.get("subscription")
        if not isinstance(sub_info, dict) or not sub_info.get("endpoint"):
            continue
        notify_ids = normalize_notify_exchange_ids(env.get("notify_exchanges"))
        payloads: list[dict[str, str]]
        if per_coin_api:
            ent_f, ext_f = filter_events_for_subscriber(notify_ids, entered_coins, exited_coins)
            if not ent_f and not ext_f:
                kept.append(env)
                continue
            payloads = []
            for coin in ent_f:
                payloads.append(_entry_notification_payload(coin, url))
            for coin in ext_f:
                payloads.append(_exit_notification_payload(coin, url))
        else:
            payloads = [
                {
                    "title": title_default,
                    "body": msg_default,
                    "url": url,
                    "tag": _trim(f"q-legacy-{secrets.token_hex(4)}", 64),
                }
            ]

        endpoint_removed = False
        for event_payload in payloads:
            payload = json.dumps(event_payload, separators=(",", ":"))
            try:
                webpush(
                    subscription_info=sub_info,
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims={"sub": f"mailto:{vapid_email}"},
                    ttl=86400,
                )
                sent += 1
            except WebPushException as e:
                status = getattr(e.response, "status_code", None) if e.response else None
                if status in (404, 410):
                    removed += 1
                    endpoint_removed = True
                    break
                _logger.warning("webpush failed: %s", e)
                failed += 1
            except Exception as e:
                _logger.warning("webpush error: %s", e)
                failed += 1

        if endpoint_removed:
            continue
        kept.append(env)

    with _lock:
        _save_subscriptions(kept)

    return jsonify({"sent": sent, "failed": failed, "removed": removed})
