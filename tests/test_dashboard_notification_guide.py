"""Static dashboard notification-guide regression checks."""

from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "app.js"


def test_tier_b_guide_never_unsubscribes_existing_user() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    guide_handler = source.split(
        'elNotifyGuideEnableTierB.addEventListener("click"', 1
    )[1].split("if (elNotifyGuideDialog)", 1)[0]

    assert "await enableTierBPushDirect();" in guide_handler
    assert "allowUnsubscribe" not in guide_handler
    assert source.count("enableTierBPushDirect({ allowUnsubscribe: true })") == 1
