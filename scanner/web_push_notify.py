"""Tier-B Web Push worker hook (Milestone Q21; I2 scanner extract)."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.logger import app_logger


def maybe_notify_web_push_scan() -> None:
    """POST to optional push relay after a successful scan (no market HTTP; best-effort)."""
    base = os.getenv("WEB_PUSH_NOTIFY_URL", "").strip().rstrip("/")
    secret = os.getenv("WEB_PUSH_INTERNAL_SECRET", "").strip()
    if not base or not secret:
        return
    dashboard_url = os.getenv("WEB_PUSH_DASHBOARD_URL", "").strip()
    body = json.dumps(
        {
            "title": "Linear Trend Spotter",
            "body": "Scan updated — open the qualified dashboard for the latest snapshot.",
            "url": dashboard_url or "",
        },
        separators=(",", ":"),
    ).encode("utf-8")
    req = Request(
        f"{base}/internal/notify-scan",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=45) as resp:
            _ = resp.read()
        app_logger.info("🔔 Web push relay notified (Tier B)")
    except HTTPError as he:
        app_logger.warning("⚠️ Web push relay HTTP %s: %s", he.code, he.reason)
    except URLError as ue:
        app_logger.warning("⚠️ Web push relay failed: %s", ue)
    except Exception as wp_err:
        app_logger.warning("⚠️ Web push relay failed: %s", wp_err)
