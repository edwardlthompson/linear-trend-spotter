"""Watchlist near-miss rows and optional CSV/JSON export (Milestone L3)."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


def compute_watchlist_rows(
    all_processed: list[dict[str, Any]],
    final_symbols: set[str],
    *,
    uniformity_min_score: int,
    watchlist_score_buffer: int,
) -> list[dict[str, Any]]:
    """Coins that almost qualified: near uniformity threshold or strong uniformity but non-positive 30d return.

    Excludes symbols already in ``final_symbols`` (qualified list).
    """
    low = int(uniformity_min_score) - int(watchlist_score_buffer)
    final_upper = {str(s).upper() for s in final_symbols}
    rows: list[dict[str, Any]] = []

    for c in all_processed:
        sym = str(c.get("symbol", "") or "").upper()
        if not sym or sym in final_upper:
            continue
        score = float(c.get("uniformity_score", 0.0) or 0.0)
        tg = float(c.get("total_gain", 0.0) or 0.0)
        if score >= uniformity_min_score and tg <= 0:
            reason = "uniformity_ok_return_nonpositive"
        elif tg > 0 and low <= score < uniformity_min_score:
            reason = "near_uniformity_threshold"
        else:
            continue

        rows.append(
            {
                "symbol": c.get("symbol"),
                "name": c.get("name"),
                "uniformity_score": round(score, 2),
                "total_gain_30d_pct": round(tg, 4),
                "watch_reason": reason,
                "ohlcv_source": c.get("ohlcv_source"),
                "data_reliability_score": c.get("data_reliability_score"),
                "data_reliability_label": c.get("data_reliability_label"),
            }
        )

    rows.sort(key=lambda r: (-float(r.get("uniformity_score") or 0.0), str(r.get("symbol") or "").upper()))
    return rows


def write_watchlist_exports(
    data_dir: Path,
    csv_filename: str,
    json_filename: str,
    rows: list[dict[str, Any]],
) -> None:
    """Write CSV + JSON atomically under ``data_dir``."""
    data_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": 1,
        "updated_at": now,
        "count": len(rows),
        "rows": rows,
    }

    json_path = data_dir / json_filename.strip()
    csv_path = data_dir / csv_filename.strip()
    tmp_json = data_dir / f".{json_filename.strip()}.tmp"
    tmp_csv = data_dir / f".{csv_filename.strip()}.tmp"

    try:
        tmp_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        with tmp_csv.open("w", encoding="utf-8", newline="") as handle:
            w = csv.writer(handle)
            w.writerow(
                [
                    "symbol",
                    "name",
                    "uniformity_score",
                    "total_gain_30d_pct",
                    "watch_reason",
                    "ohlcv_source",
                    "data_reliability_score",
                    "data_reliability_label",
                ]
            )
            for r in rows:
                w.writerow(
                    [
                        r.get("symbol", ""),
                        r.get("name", ""),
                        r.get("uniformity_score", ""),
                        r.get("total_gain_30d_pct", ""),
                        r.get("watch_reason", ""),
                        r.get("ohlcv_source", ""),
                        r.get("data_reliability_score", ""),
                        r.get("data_reliability_label", ""),
                    ]
                )
        tmp_json.replace(json_path)
        tmp_csv.replace(csv_path)
    except OSError as exc:
        _logger.warning("Watchlist export failed: %s", exc)
        for p in (tmp_json, tmp_csv):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        raise
