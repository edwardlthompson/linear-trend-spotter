#!/usr/bin/env python3
"""Fail if exchange_data uses non-ASCII on lines containing print().

Background: on Windows, cp1252 consoles raise UnicodeEncodeError when print()
emits emoji or other non-ASCII. That can abort the listings refresh and leave
exchange_listings empty (scanner falls back to a tiny symbol set or appears
"broken"). CI runs this script to catch regressions.

Usage (repo root):
  python scripts/check_exchange_print_ascii.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _scan_dir(repo_root: Path, package_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(package_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if "print(" not in line:
                continue
            try:
                line.encode("ascii")
            except UnicodeEncodeError:
                try:
                    rel = path.relative_to(repo_root)
                except ValueError:
                    rel = path
                errors.append(f"{rel}:{i}: non-ASCII in print() line (breaks Windows cp1252 console)")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "paths",
        nargs="*",
        help="Directories to scan (default: exchange_data under repo root)",
    )
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    dirs = [Path(x) for x in args.paths] if args.paths else [root / "exchange_data"]
    all_errors: list[str] = []
    for d in dirs:
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            return 2
        all_errors.extend(_scan_dir(root, d))
    if all_errors:
        for msg in all_errors:
            print(msg, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
