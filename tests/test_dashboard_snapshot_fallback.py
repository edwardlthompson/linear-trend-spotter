"""Static regression checks for dashboard snapshot fallback behavior."""

from __future__ import annotations

from pathlib import Path


APP_JS = Path("docs/dashboard/app.js")


def test_dashboard_fallback_covers_non_503_primary_failures() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "fetchCommittedSnapshotFallback" in source
    assert "network error" in source
    assert "res.status === 503 && fallback" not in source


def test_dashboard_committed_fallback_does_not_advance_notification_baselines() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "if (usedCommittedFallback) {\n        return;\n      }\n      if (forNotify && notifyAlertsEnabled)" in source
