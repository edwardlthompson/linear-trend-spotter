"""Pytest: ensure DATA_DIR is writable before config.settings loads.

Render sets DATA_DIR=/var/data for builds, but the disk is mounted only at
runtime — importing notifications (→ settings) during pytest would mkdir
/var/data and fail with Errno 30. Use a temp directory for tests.
"""

from __future__ import annotations

import os
import tempfile


def _ensure_writable_data_dir() -> None:
    raw = os.environ.get("DATA_DIR", "").strip()
    # Render build: /var/data exists but is read-only until deploy mounts the disk.
    if raw == "/var/data":
        os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="lts_pytest_")


_ensure_writable_data_dir()
