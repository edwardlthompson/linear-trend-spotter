"""Regression checks for dashboard relay-fallback alert baselines."""

from __future__ import annotations

import re
from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "app.js"


def _source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_committed_relay_fallback_does_not_write_snapshot_digest_baselines() -> None:
    src = _source()

    assert "render(data, { suppressSnapshotSideEffects: usedRelay503Fallback });" in src
    assert re.search(
        r"if \(usedRelay503Fallback\) \{\s*return;\s*\}\s*const snapDigest = await digestHex\(text\);",
        src,
    )


def test_committed_relay_fallback_render_suppresses_alert_side_effects() -> None:
    src = _source()

    assert "const suppressSnapshotSideEffects = Boolean(options && options.suppressSnapshotSideEffects);" in src
    assert "const prevSyms = suppressSnapshotSideEffects ? new Set() : readPrevSymbolSet();" in src
    assert "lastPinWatchDelta = suppressSnapshotSideEffects" in src
    assert "const listNotifyDelta = suppressSnapshotSideEffects" in src
    assert "if (!suppressSnapshotSideEffects && schemaChanged)" in src
    assert re.search(
        r"if \(!suppressSnapshotSideEffects\) \{\s*writeSnapshotVisitState\(data\);\s*\}",
        src,
    )
