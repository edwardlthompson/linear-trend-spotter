"""Optional per-scan API cost artifact (Milestone J3)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_last_completed_coingecko_http_total(metrics_path: Path) -> int | None:
    """Last entry in metrics.json history (prior scan), for J4 degrade gate."""
    if not metrics_path.exists():
        return None
    try:
        raw = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            return None
        last = raw[-1]
        counts = last.get("counts") if isinstance(last, dict) else None
        if not isinstance(counts, dict):
            return None
        v = counts.get("coingecko_http_total")
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def build_scan_costs_payload(metrics_summary: dict[str, Any]) -> dict[str, Any]:
    counts = dict(metrics_summary.get("counts") or {})
    coingecko = {k: int(v) for k, v in counts.items() if k.startswith("coingecko_http_")}
    out: dict[str, Any] = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "coingecko_http": coingecko,
        "polygon_http_total": int(counts.get("polygon_http_total", 0)),
        "polygon_http_aggs": int(counts.get("polygon_http_aggs", 0)),
        "polygon_http_other": int(counts.get("polygon_http_other", 0)),
        "cmc_http_total": int(counts.get("cmc_http_total", 0)),
        "cmc_http_listings": int(counts.get("cmc_http_listings", 0)),
        "cmc_http_ohlcv": int(counts.get("cmc_http_ohlcv", 0)),
        "cmc_http_other": int(counts.get("cmc_http_other", 0)),
        "cache_hits": dict(metrics_summary.get("cache_hits") or {}),
        "cache_misses": dict(metrics_summary.get("cache_misses") or {}),
        "api_calls": dict(metrics_summary.get("api_calls") or {}),
        "coins_processed": int(metrics_summary.get("coins_processed", 0) or 0),
    }
    return out


def write_scan_costs_file(data_dir: Path, filename: str, metrics_summary: dict[str, Any]) -> None:
    payload = build_scan_costs_payload(metrics_summary)
    path = data_dir / filename
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
