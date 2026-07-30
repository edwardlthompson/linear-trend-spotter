"""Static regression checks for dashboard snapshot fallback control flow."""

from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "app.js"


def _load_snapshot_body() -> str:
    text = APP_JS.read_text(encoding="utf-8")
    start = text.index("async function loadSnapshot")
    end = text.index("  function startPoll", start)
    return text[start:end]


def test_load_snapshot_falls_back_for_any_primary_failure() -> None:
    body = _load_snapshot_body()

    assert "primaryFetchError" in body
    assert "if ((!res || !res.ok) && fallback && fallback !== primary)" in body
    assert "res.status === 503 && fallback" not in body


def test_committed_fallback_does_not_advance_notification_baselines() -> None:
    body = _load_snapshot_body()

    assert "forNotify && notifyAlertsEnabled && !snapshotLoadWasCommittedFallback" in body
    assert "notifyAlertsEnabled && !snapshotLoadWasCommittedFallback" in body
