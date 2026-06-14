"""Tier-C ntfy bridge (Milestone Q23b).

When ``NTFY_ENABLED`` and topic settings are configured, the worker POSTs a short
list-change message to ntfy after qualified entries/exits (same gate as Tier-B).
No OHLCV or market payloads — title/body text only.
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from config.settings import settings
from scanner.web_push_notify import build_qualified_change_push_copy
from utils.logger import app_logger


def _ntfy_publish_url() -> str | None:
    if not settings.ntfy_enabled:
        return None
    base = str(settings.ntfy_base_url or "").strip().rstrip("/")
    topic = str(settings.ntfy_topic or "").strip()
    if not base or not topic:
        return None
    return f"{base}/{quote(topic, safe='')}"


def _post_ntfy(title: str, body: str, *, dashboard_url: str) -> bool:
    url = _ntfy_publish_url()
    if not url:
        return False
    headers: dict[str, str] = {
        "Title": title[:250],
        "Priority": settings.ntfy_priority,
        "Tags": "chart_with_upwards_trend",
    }
    token = str(settings.ntfy_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if dashboard_url.strip():
        headers["Click"] = dashboard_url.strip()[:2000]
    msg = body.strip() or "Open the qualified dashboard for the latest snapshot."
    if len(msg) > 4000:
        msg = msg[:3997] + "…"
    req = Request(url, data=msg.encode("utf-8"), method="POST", headers=headers)
    with urlopen(req, timeout=20) as resp:
        _ = resp.read()
    return True


def maybe_notify_ntfy_qualified_changes(
    entered: list[Mapping[str, Any]] | None,
    exited: list[Mapping[str, Any]] | None,
) -> None:
    """POST to optional ntfy topic when the qualified set gained or lost members."""
    if not settings.ntfy_enabled:
        return
    if not (entered or exited):
        return
    if not _ntfy_publish_url():
        app_logger.warning("⚠️ NTFY_ENABLED but NTFY_BASE_URL or NTFY_TOPIC missing; skipping")
        return
    title, body = build_qualified_change_push_copy(entered=entered, exited=exited)
    dashboard_url = str(settings.ntfy_dashboard_url or "").strip()
    try:
        if _post_ntfy(title, body, dashboard_url=dashboard_url):
            app_logger.info(
                "🔔 ntfy notified (qualified in=%s out=%s)",
                len(entered or []),
                len(exited or []),
            )
    except HTTPError as he:
        app_logger.warning("⚠️ ntfy HTTP %s: %s", he.code, he.reason)
    except URLError as ue:
        app_logger.warning("⚠️ ntfy request failed: %s", ue)
    except Exception as err:
        app_logger.warning("⚠️ ntfy notify failed: %s", err)
