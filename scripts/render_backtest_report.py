"""Render final backtest ranked table and top-settings block from JSON artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.report import render_ranked_table, rows_from_summary, top_settings_block
from config.settings import settings


def main() -> int:
    artifact = settings.base_dir / "backtest_results.json"
    if not artifact.exists():
        print(f"FAIL: artifact not found: {artifact}")
        return 1

    summary = json.loads(artifact.read_text(encoding="utf-8"))
    rows = rows_from_summary(summary)
    if not rows:
        print("FAIL: no result rows in artifact")
        return 1

    print(render_ranked_table(rows))
    print()
    print(top_settings_block(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
