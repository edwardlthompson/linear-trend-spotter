"""Static regression checks for dashboard committed-snapshot fallback behavior."""

from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "app.js"


def test_committed_fallback_does_not_advance_notification_baselines() -> None:
    src = APP_JS.read_text(encoding="utf-8")

    assert "if (usedCommittedFallback) {\n        return;\n      }\n      if (forNotify && notifyAlertsEnabled)" in src
    assert "if (!snapshotLoadWasCommittedFallback) {\n      writeSnapshotVisitState(data);\n    }" in src
    assert "snapshotLoadWasCommittedFallback || prevSyms.size === 0" in src
    assert "lastPinWatchDelta = { entered: [], left: [] };" in src


def test_committed_fallback_covers_http_and_network_failures() -> None:
    src = APP_JS.read_text(encoding="utf-8")

    assert "primaryFetchError = fetchErr;" in src
    assert "if ((!res || !res.ok) && fallback && fallback !== primary)" in src
    assert "Showing committed docs/qualified_public_snapshot.json because the live snapshot request failed" in src
