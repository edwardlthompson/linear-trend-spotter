#!/usr/bin/env python3
"""Serve the qualified-coin dashboard from your PC — no GitHub Pages or Render.

Serves ``docs/`` at http://127.0.0.1:<port>/ and maps GET /qualified_public_snapshot.json
to the file under DATA_DIR (same place the scanner writes after a successful scan when
PUBLIC_QUALIFIED_SNAPSHOT_ENABLED is true).

Usage (from repo root, after ``python main.py`` or your Render-backed scan has produced the JSON):

  python scripts/local_dashboard.py

Optional:

  python scripts/local_dashboard.py --port 8765
  python scripts/local_dashboard.py --source "D:\\data\\qualified_public_snapshot.json"
  python scripts/local_dashboard.py --no-open

Press Ctrl+C to stop.

Loads ``.env`` if python-dotenv is installed (same as other scripts) so DATA_DIR can live there.
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DEFAULT_SNAPSHOT_NAME = "qualified_public_snapshot.json"

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]


def _resolve_snapshot_path(args: argparse.Namespace) -> Path:
    if args.source:
        return Path(args.source).expanduser().resolve()
    data_dir = (args.data_dir or os.getenv("DATA_DIR", "")).strip()
    if not data_dir:
        guess = ROOT / ".render-data"
        data_dir = str(guess) if guess.is_dir() else str(ROOT)
    return Path(data_dir).expanduser().resolve() / DEFAULT_SNAPSHOT_NAME


def main() -> int:
    if load_dotenv:
        load_dotenv(ROOT / ".env")

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="Port (default 8765)")
    p.add_argument("--data-dir", default="", help="Folder containing qualified_public_snapshot.json")
    p.add_argument("--source", default="", help="Full path to qualified_public_snapshot.json")
    p.add_argument("--no-open", action="store_true", help="Do not open a browser tab")
    args = p.parse_args()

    snapshot_path = _resolve_snapshot_path(args)
    if not snapshot_path.is_file():
        print(f"Snapshot not found: {snapshot_path}", file=sys.stderr)
        print(
            "Run a scan first with PUBLIC_QUALIFIED_SNAPSHOT_ENABLED true in config.json, "
            "or pass --source / --data-dir.",
            file=sys.stderr,
        )
        return 1

    if not DOCS.is_dir():
        print(f"Missing docs folder: {DOCS}", file=sys.stderr)
        return 1

    snap_abs = snapshot_path.resolve()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DOCS), **kw)

        def do_GET(self) -> None:  # noqa: N802
            norm = self.path.split("?", 1)[0].rstrip("/") or "/"
            if norm == "/qualified_public_snapshot.json":
                try:
                    body = snap_abs.read_bytes()
                except OSError as e:
                    self.send_error(500, f"Cannot read snapshot: {e}")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if norm in ("/", ""):
                self.send_response(302)
                self.send_header("Location", "/dashboard/")
                self.end_headers()
                return
            super().do_GET()

        def log_message(self, fmt: str, *log_args: object) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % log_args))

    url = f"http://{args.host}:{args.port}/dashboard/"
    print(f"Serving dashboard from {DOCS}")
    print(f"Snapshot file: {snap_abs}")
    print(f"Open: {url}")
    print("Ctrl+C to stop.")

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    if not args.no_open:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
