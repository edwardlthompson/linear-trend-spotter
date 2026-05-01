"""Optional post-scan artifacts (heartbeat, public snapshot). Default off."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmpp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmpp, path)
    finally:
        if os.path.exists(tmpp):
            try:
                os.remove(tmpp)
            except OSError:
                pass


def write_scan_heartbeat(
    data_dir: Path,
    *,
    filename: str,
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Write a small JSON heartbeat after a scan (J2)."""
    end = finished_at or datetime.now(timezone.utc)
    duration_s = max(0.0, (end - started_at).total_seconds())
    body: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": end.isoformat(),
        "duration_seconds": round(duration_s, 3),
    }
    if extra:
        body.update(extra)
    _atomic_write_json(data_dir / filename, body)


def build_public_qualified_snapshot(
    final_results: list[dict[str, Any]],
    *,
    field_set: str = "full",
) -> dict[str, Any]:
    """Notification-parity subset for public JSON (Q1/Q2). No secrets.

    field_set: ``full`` matches notification-oriented rows; ``minimal`` omits
    exchange volume breakdown and OHLCV provenance for smaller public payloads (Q3).
    """
    coins_out: list[dict[str, Any]] = []
    minimal = str(field_set or "full").strip().lower() == "minimal"
    for row in final_results:
        gains = row.get("gains") or {}
        coin: dict[str, Any] = {
            "symbol": str(row.get("symbol", "")).upper(),
            "name": str(row.get("name", "")),
            "slug": row.get("slug"),
            "source_url": row.get("source_url") or row.get("cmc_url"),
            "gains": {
                "7d": float(gains.get("7d", 0) or 0),
                "30d": float(gains.get("30d", 0) or 0),
            },
            "uniformity_score": float(row.get("uniformity_score", 0) or 0),
            "health_score": row.get("health_score"),
            "current_rank": row.get("current_rank"),
            "rank_delta": row.get("rank_delta"),
        }
        if not minimal:
            coin["exchange_volumes"] = row.get("exchange_volumes")
            coin["volume_24h"] = row.get("volume_24h")
            coin["ohlcv_source"] = row.get("ohlcv_source")
        coins_out.append(coin)
    return {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "field_set": "minimal" if minimal else "full",
        "coins": coins_out,
    }


def write_public_qualified_snapshot(
    data_dir: Path,
    filename: str,
    final_results: list[dict[str, Any]],
    *,
    field_set: str = "full",
) -> None:
    payload = build_public_qualified_snapshot(final_results, field_set=field_set)
    _atomic_write_json(data_dir / filename, payload)
