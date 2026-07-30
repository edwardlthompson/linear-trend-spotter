"""Static dashboard asset integrity tests."""

from __future__ import annotations

import json
import re
from pathlib import Path


DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "docs" / "dashboard"


def test_service_worker_precache_assets_exist() -> None:
    sw = (DASHBOARD_DIR / "sw.js").read_text(encoding="utf-8")
    assets_match = re.search(r"const ASSETS = \[(.*?)\];", sw, flags=re.S)
    assert assets_match is not None
    assets = re.findall(r'"([^"]+)"', assets_match.group(1))

    missing = []
    for asset in assets:
        if not asset.startswith("./"):
            continue
        if not (DASHBOARD_DIR / asset[2:]).exists():
            missing.append(asset)

    assert missing == []


def test_manifest_icons_exist() -> None:
    manifest = json.loads((DASHBOARD_DIR / "manifest.webmanifest").read_text(encoding="utf-8"))
    missing = []
    for icon in manifest.get("icons", []):
        src = str(icon.get("src", ""))
        if src.startswith("./") and not (DASHBOARD_DIR / src[2:]).exists():
            missing.append(src)

    assert missing == []
