#!/usr/bin/env python3
"""Copy qualified_public_snapshot.json from DATA_DIR into docs/ for GitHub Pages (same-origin, no Render relay).

After a local or server scan, run from the repo root:

  python scripts/sync_snapshot_to_docs.py

Optional:

  python scripts/sync_snapshot_to_docs.py --data-dir "C:/path/to/DATA_DIR"
  python scripts/sync_snapshot_to_docs.py --source /path/to/qualified_public_snapshot.json

Then: git add docs/qualified_public_snapshot.json && git commit -m "Update snapshot" && git push

The dashboard default URL is ../qualified_public_snapshot.json (served from this repo on Pages).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_JSON = ROOT / "docs" / "qualified_public_snapshot.json"
DEFAULT_NAME = "qualified_public_snapshot.json"

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]


def main() -> int:
    if load_dotenv:
        load_dotenv(ROOT / ".env")

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-dir",
        default="",
        help="Directory containing the snapshot (default: env DATA_DIR, else ./.render-data, else repo root).",
    )
    p.add_argument(
        "--source",
        default="",
        help=f"Full path to {DEFAULT_NAME} (overrides --data-dir).",
    )
    args = p.parse_args()

    if args.source:
        src = Path(args.source).expanduser()
    else:
        data_dir = (args.data_dir or os.getenv("DATA_DIR", "")).strip()
        if not data_dir:
            guess = ROOT / ".render-data"
            data_dir = str(guess) if guess.is_dir() else str(ROOT)
        src = Path(data_dir).expanduser() / DEFAULT_NAME

    if not src.is_file():
        print(f"Not found: {src}", file=sys.stderr)
        print("Run a scan first, or set --data-dir / --source.", file=sys.stderr)
        return 1

    DOCS_JSON.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DOCS_JSON)
    print(f"Copied {src} -> {DOCS_JSON}")
    print("Next: git add docs/qualified_public_snapshot.json && git commit && git push (Pages deploys in ~1–2 min).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
