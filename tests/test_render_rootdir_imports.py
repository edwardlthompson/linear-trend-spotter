"""Import smoke tests for Render services that set rootDir to a subfolder.

If these fail, the web service will not start (e.g. ModuleNotFoundError:
push_server). Mirrors Render layout: cwd == service folder; ``import app``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _import_app_ok(cwd: Path) -> None:
    r = subprocess.run(
        [sys.executable, "-c", "import app; assert getattr(app, 'app', None) is not None"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"


def test_push_server_uv_run_gunicorn_module() -> None:
    """Render start uses uv run gunicorn --chdir push_server; ensure app module loads."""
    r = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-c",
            "import app; assert getattr(app, 'app', None) is not None",
        ],
        cwd=str(ROOT / "push_server"),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"


def test_push_server_import_with_cwd_push_server() -> None:
    _import_app_ok(ROOT / "push_server")


def test_snapshot_server_import_with_cwd_snapshot_server() -> None:
    _import_app_ok(ROOT / "snapshot_server")
