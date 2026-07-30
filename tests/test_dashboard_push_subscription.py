"""Static regression checks for Tier-B push subscription recovery."""

from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "app.js"


def test_existing_push_subscription_is_registered_on_page_load() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    start = src.index('window.addEventListener("load"')
    end = src.index('document.addEventListener("visibilitychange"', start)
    body = src[start:end]

    register_at = body.index("await registerServiceWorker();")
    sync_at = body.index("await syncPushNotifyExchangesIfSubscribed();")
    assert register_at < sync_at
