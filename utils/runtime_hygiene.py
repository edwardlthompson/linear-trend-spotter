"""Runtime hygiene and analytics utilities."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ARTIFACT_PATTERNS = [
    "benchmark_*.log",
    "benchmark_*.json",
    "benchmark_*_error.txt",
    "*_stdout.log",
    "*_stderr.log",
    "run_*.log",
    "bot_output.log",
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_artifact_hygiene(base_dir: Path, archive_dir: Path, retention_days: int) -> dict[str, Any]:
    """Archive old generated artifacts from repository root.

    This intentionally targets only known generated file patterns to avoid moving
    source files or required runtime state.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(retention_days)))
    timestamp_dir = archive_dir / datetime.now().strftime("%Y%m%d")
    archived: list[str] = []

    for pattern in ARTIFACT_PATTERNS:
        for file_path in base_dir.glob(pattern):
            if not file_path.is_file():
                continue
            if file_path.resolve().is_relative_to(archive_dir.resolve()):
                continue

            modified = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if modified >= cutoff:
                continue

            timestamp_dir.mkdir(parents=True, exist_ok=True)
            destination = timestamp_dir / file_path.name
            if destination.exists():
                destination = timestamp_dir / f"{file_path.stem}_{int(modified.timestamp())}{file_path.suffix}"
            shutil.move(str(file_path), str(destination))
            archived.append(file_path.name)

    return {
        "timestamp": _iso_now(),
        "retention_days": int(retention_days),
        "archived_count": len(archived),
        "archived_files": sorted(archived),
        "archive_dir": str(timestamp_dir),
    }


def update_exit_reason_analytics(analytics_file: Path, exited_coins: list[dict[str, Any]]) -> dict[str, Any]:
    """Persist cumulative and per-run exit-reason stats."""
    reason_counts_this_run: dict[str, int] = {}
    for coin in exited_coins:
        reason = str(coin.get("exit_reason") or "No longer met qualification criteria").strip()
        reason_counts_this_run[reason] = reason_counts_this_run.get(reason, 0) + 1

    payload: dict[str, Any]
    if analytics_file.exists():
        try:
            payload = json.loads(analytics_file.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    else:
        payload = {}

    total_runs = int(payload.get("total_runs", 0)) + 1
    total_exits = int(payload.get("total_exits", 0)) + sum(reason_counts_this_run.values())
    cumulative = dict(payload.get("reason_counts", {}))

    for reason, count in reason_counts_this_run.items():
        cumulative[reason] = int(cumulative.get(reason, 0)) + int(count)

    payload = {
        "updated_at": _iso_now(),
        "total_runs": total_runs,
        "total_exits": total_exits,
        "reason_counts": dict(sorted(cumulative.items(), key=lambda item: item[1], reverse=True)),
        "last_run": {
            "timestamp": _iso_now(),
            "exits": sum(reason_counts_this_run.values()),
            "reason_counts": dict(sorted(reason_counts_this_run.items(), key=lambda item: item[1], reverse=True)),
        },
    }

    analytics_file.parent.mkdir(parents=True, exist_ok=True)
    analytics_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
