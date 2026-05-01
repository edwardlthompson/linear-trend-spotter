#!/usr/bin/env python3
"""Milestone P3: AST scan — backtesting must not import Telegram / main / notifications."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_TOP = frozenset({"notifications", "telegram_bot", "main"})


def _violations_in_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = (alias.name or "").split(".", 1)[0]
                if top in FORBIDDEN_TOP:
                    out.append(f"{path}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            top = base.split(".", 1)[0] if base else ""
            if top in FORBIDDEN_TOP:
                level = getattr(node, "level", 0) or 0
                if level == 0:
                    out.append(f"{path}: from {base}")
    return out


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    bad: list[str] = []
    for path in sorted((root / "backtesting").rglob("*.py")):
        bad.extend(_violations_in_file(path))
    if bad:
        for line in bad:
            print(f"FAIL: {line}")
        return 1
    print("PASS: backtesting import guard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
