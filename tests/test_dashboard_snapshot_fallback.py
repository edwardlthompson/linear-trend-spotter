"""Dashboard snapshot fallback policy regressions."""

from __future__ import annotations

from pathlib import Path


def test_committed_snapshot_fallback_is_disabled_for_notification_polls() -> None:
    app_js = Path("docs/dashboard/app.js").read_text(encoding="utf-8")

    assert "const forNotify = options && options.forNotify;" in app_js
    assert (
        "if (!forNotify && !res.ok && res.status === 503 && fallback && fallback !== primary)"
        in app_js
    )

