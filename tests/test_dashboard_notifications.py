"""Dashboard notification wiring regressions."""

from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "app.js"


def _section(source: str, start: str, end: str) -> str:
    start_idx = source.index(start)
    end_idx = source.index(end, start_idx)
    return source[start_idx:end_idx]


def test_qualified_tier_a_system_notifications_are_filter_aware_only() -> None:
    """The render path may update the in-app feed, but OS alerts must respect filters."""
    source = APP_JS.read_text(encoding="utf-8")

    render_section = _section(source, "function render(data) {", "  if (elTbody) {")
    assert "appendQualifiedListNotifications(" in render_section
    assert "showDashboardNotification(" not in render_section

    filtered_poll_section = _section(
        source,
        "async function notifySnapshotChangedFiltered(data, nextDigest) {",
        "  /** Tier-A: notify when a watched symbol enters",
    )
    assert "showDashboardNotification(" in filtered_poll_section
    assert "New in filtered view:" in filtered_poll_section
    assert "Removed from filtered view:" in filtered_poll_section
