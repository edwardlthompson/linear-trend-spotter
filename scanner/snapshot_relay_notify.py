"""Push public snapshot JSON to optional HTTPS relay after worker writes disk copy."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.logger import app_logger


def maybe_push_qualified_snapshot_relay(data_dir: Path, filename: str) -> None:
    """POST file bytes to relay when QUALIFIED_SNAPSHOT_RELAY_* env vars are set."""
    base = os.getenv("QUALIFIED_SNAPSHOT_RELAY_URL", "").strip().rstrip("/")
    secret = os.getenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "").strip()
    if not base or not secret:
        return
    path = data_dir / filename
    if not path.is_file():
        app_logger.warning("⚠️ Snapshot relay skipped: missing %s", path)
        return
    try:
        body = path.read_bytes()
    except OSError as e:
        app_logger.warning("⚠️ Snapshot relay read failed: %s", e)
        return
    req = Request(
        f"{base}/internal/ingest-snapshot",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=120) as resp:
            _ = resp.read()
        app_logger.info("📡 Qualified snapshot relay updated")
    except HTTPError as he:
        app_logger.warning("⚠️ Snapshot relay HTTP %s: %s", he.code, he.reason)
    except URLError as ue:
        app_logger.warning("⚠️ Snapshot relay failed: %s", ue)
    except Exception as ex:
        app_logger.warning("⚠️ Snapshot relay failed: %s", ex)
