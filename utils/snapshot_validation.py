"""Validate public qualified snapshot payloads for dashboard and ops confidence."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def _iso_age_ok(iso: str) -> bool:
    raw = str(iso or "").strip()
    if not raw:
        return False
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()
        return math.isfinite(age) and -3600 <= age <= 86400 * 400
    except ValueError:
        return False


def validate_public_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a serializable ``snapshot_validation`` block (issues, stats, level).

    ``level`` is ``ok`` | ``warn`` | ``error`` — error means likely unusable JSON shape.
    """
    issues: list[str] = []
    stats: dict[str, Any] = {}

    if not isinstance(payload, dict):
        return {
            "schema_version": 1,
            "ok": False,
            "level": "error",
            "issues": ["payload is not an object"],
            "stats": {},
        }

    sv = payload.get("schema_version")
    if not isinstance(sv, int) or sv < 1:
        issues.append("missing or invalid schema_version")

    updated = str(payload.get("updated_at") or "").strip()
    if not updated:
        issues.append("missing updated_at")
    elif not _iso_age_ok(updated):
        issues.append("updated_at missing or not a plausible ISO timestamp")

    coins = payload.get("coins")
    if not isinstance(coins, list):
        issues.append("coins must be an array")
        coins = []

    n = len(coins)
    stats["coin_count"] = n

    with_symbol = 0
    with_h1 = 0
    with_gains = 0
    for c in coins:
        if not isinstance(c, dict):
            continue
        if str(c.get("symbol") or "").strip():
            with_symbol += 1
        g = c.get("gains")
        if isinstance(g, dict) and isinstance(g.get("7d"), (int, float)) and isinstance(g.get("30d"), (int, float)):
            with_gains += 1
        h = c.get("closes_1h")
        if isinstance(h, list) and len(h) >= 8:
            with_h1 += 1

    stats["coins_with_symbol"] = with_symbol
    stats["coins_with_gains_7d_30d"] = with_gains
    stats["coins_with_closes_1h"] = with_h1

    if n > 0 and with_symbol < n:
        issues.append(f"{n - with_symbol} coin row(s) missing symbol")
    if n > 0 and with_gains < max(1, int(n * 0.5)) and with_gains < n:
        issues.append("many coins lack gains.7d / gains.30d — snapshot may be partial")

    interval = payload.get("scan_interval_seconds")
    if interval is not None:
        try:
            iv = int(interval)
            if iv < 60 or iv > 604800:
                issues.append("scan_interval_seconds outside expected 60–604800")
            else:
                stats["scan_interval_seconds"] = iv
        except (TypeError, ValueError):
            issues.append("scan_interval_seconds not an integer")

    level = "ok"
    if not isinstance(payload.get("coins"), list):
        level = "error"
    elif issues:
        level = "warn"

    return {
        "schema_version": 1,
        "ok": level != "error",
        "level": level,
        "issues": issues,
        "stats": stats,
    }
