"""Print or validate the latest watchlist export under DATA_DIR (Milestone L3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import Settings, settings as global_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Show watchlist export row count and path")
    parser.add_argument(
        "--config",
        default=None,
        help="Optional path to config.json (else default discovery)",
    )
    args = parser.parse_args()
    cfg = Settings(config_path=args.config) if args.config else global_settings
    path = cfg.base_dir / str(cfg.watchlist_export_json_file).strip()
    if not path.exists():
        print(f"No export file at {path} (enable WATCHLIST_EXPORT_ENABLED and run a scan).", file=sys.stderr)
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 2
    n = int(data.get("count", 0))
    print(f"OK {path} | rows={n} | updated_at={data.get('updated_at', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
