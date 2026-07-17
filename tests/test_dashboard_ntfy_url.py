"""Static regression checks for dashboard ntfy subscribe URL safety."""

from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "docs" / "dashboard" / "app.js"


def test_ntfy_subscribe_links_require_https() -> None:
    src = APP_JS.read_text(encoding="utf-8")

    assert 'return parsed.protocol === "https:" ? parsed.href : "";' in src
    assert "return safeExternalHttpsUrl(window.__NTFY_SUBSCRIBE_URL__);" in src
    assert "const fromSnap = safeExternalHttpsUrl(snapshotNtfySubscribeUrl);" in src
    assert "snapshotNtfySubscribeUrl = safeExternalHttpsUrl(url);" in src
