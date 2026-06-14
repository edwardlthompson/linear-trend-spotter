"""Optional post-scan artifacts (heartbeat, public snapshot). Default off."""

from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.snapshot_validation import validate_public_snapshot


def _risk_context_from_hourly_closes(closes: list[float]) -> dict[str, Any] | None:
    """Rough risk context from hourly closes: 7d annualized hist vol, 30d max drawdown %."""
    if len(closes) < 8:
        return None
    tail7 = closes[-min(168, len(closes)) :]
    tail30 = closes[-min(720, len(closes)) :]

    lr7: list[float] = []
    for i in range(1, len(tail7)):
        a, b = tail7[i - 1], tail7[i]
        if a > 0 and b > 0:
            lr7.append(math.log(b / a))

    hv7_ann: float | None = None
    if len(lr7) >= 2:
        m = sum(lr7) / len(lr7)
        var = sum((x - m) ** 2 for x in lr7) / (len(lr7) - 1)
        std = math.sqrt(max(0.0, var))
        hv7_ann = std * math.sqrt(24 * 365) * 100
        if not math.isfinite(hv7_ann):
            hv7_ann = None

    peak = tail30[0]
    max_dd = 0.0
    for v in tail30:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd

    out: dict[str, Any] = {}
    if hv7_ann is not None:
        out["hv_7d_annualized_pct"] = round(float(hv7_ann), 2)
    out["max_drawdown_30d_pct"] = round(float(max_dd), 2)
    return out


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


def _optional_scan_health_fields(scan_health: dict[str, Any] | None) -> dict[str, Any]:
    """Q20: optional top-level snapshot fields for dashboard strip (no secrets)."""
    if not scan_health:
        return {}
    out: dict[str, Any] = {}
    raw_dur = scan_health.get("scan_duration_s")
    if isinstance(raw_dur, (int, float)):
        fd = float(raw_dur)
        if fd >= 0 and fd == fd:  # finite, non-NaN
            out["scan_duration_s"] = round(fd, 2)
    raw_ev = scan_health.get("coins_evaluated")
    if isinstance(raw_ev, int) and raw_ev >= 0:
        out["coins_evaluated"] = raw_ev
    elif isinstance(raw_ev, float) and raw_ev >= 0 and raw_ev == raw_ev:
        out["coins_evaluated"] = int(raw_ev)
    raw_err = scan_health.get("errors_count")
    if isinstance(raw_err, int) and raw_err >= 0:
        out["errors_count"] = raw_err
    elif isinstance(raw_err, float) and raw_err >= 0 and raw_err == raw_err:
        out["errors_count"] = int(raw_err)
    return out


def _public_qualification_exits(exited: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Thin list for dashboard exit lines + Tier-A copy (no PII)."""
    if not exited:
        return []
    out: list[dict[str, str]] = []
    for c in exited:
        sym = str(c.get("symbol", "")).upper().strip()
        if not sym:
            continue
        reason = str(c.get("exit_reason") or "").strip() or "No longer met qualification criteria"
        out.append({"symbol": sym, "exit_reason": reason})
    return out


def build_notify_public_config(
    *,
    ntfy_enabled: bool = False,
    ntfy_base_url: str = "",
    ntfy_topic: str = "",
) -> dict[str, Any] | None:
    """Public Tier-C hints for dashboard (subscribe URL only — never publish token)."""
    if not ntfy_enabled:
        return None
    topic = str(ntfy_topic or "").strip()
    if not topic:
        return None
    base = str(ntfy_base_url or "https://ntfy.sh").strip().rstrip("/")
    if not base:
        base = "https://ntfy.sh"
    return {"ntfy_subscribe_url": f"{base}/{topic}"}


def build_public_qualified_snapshot(
    final_results: list[dict[str, Any]],
    *,
    field_set: str = "full",
    scan_interval_seconds: int = 3600,
    scan_health: dict[str, Any] | None = None,
    regime_gate: dict[str, Any] | None = None,
    api_cost_panel: dict[str, Any] | None = None,
    qualification_exits: list[dict[str, Any]] | None = None,
    notify_public_config: dict[str, Any] | None = None,
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
            "cmc_slug": row.get("cmc_slug"),
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
        id_block = row.get("identity")
        if isinstance(id_block, dict):
            coin["identity"] = id_block
        if not minimal:
            coin["exchange_volumes"] = row.get("exchange_volumes")
            coin["listed_on"] = row.get("listed_on")
            coin["volume_24h"] = row.get("volume_24h")
            coin["ohlcv_source"] = row.get("ohlcv_source")
            if row.get("volume_acceleration_pct") is not None:
                try:
                    coin["volume_acceleration_pct"] = float(row.get("volume_acceleration_pct", 0) or 0)
                except (TypeError, ValueError):
                    pass
            if row.get("volume_acceleration_window_days") is not None:
                try:
                    coin["volume_acceleration_window_days"] = int(row.get("volume_acceleration_window_days") or 0)
                except (TypeError, ValueError):
                    pass
            strategies = row.get("backtest_top_strategies")
            if strategies is not None:
                coin["backtest_top_strategies"] = strategies
            if row.get("backtest_buy_hold") is not None:
                coin["backtest_buy_hold"] = row.get("backtest_buy_hold")
            chart_url = row.get("chart_image_url")
            if isinstance(chart_url, str) and chart_url.strip().lower().startswith("https://"):
                coin["chart_image_url"] = chart_url.strip()
            closes = row.get("closes_30d")
            if isinstance(closes, list) and len(closes) >= 2:
                try:
                    nums = [float(x) for x in closes]
                    if all(math.isfinite(x) for x in nums):
                        coin["closes_30d"] = nums
                except (TypeError, ValueError):
                    pass
            h1 = row.get("closes_1h")
            if isinstance(h1, list) and len(h1) >= 2:
                try:
                    # Dashboard 7d/30d sparklines need up to 30×24 hourly closes; do not cap at 200
                    # (200 h ≈ 8.3 d made 7d vs 30d sparklines visually identical).
                    _hour_cap = 30 * 24
                    tail = h1 if len(h1) <= _hour_cap else h1[-_hour_cap:]
                    hnums = [float(x) for x in tail]
                    if all(math.isfinite(x) for x in hnums):
                        coin["closes_1h"] = hnums
                        rc = _risk_context_from_hourly_closes(hnums)
                        if rc:
                            coin["risk_context"] = rc
                except (TypeError, ValueError):
                    pass
        coins_out.append(coin)
    interval = max(60, int(scan_interval_seconds or 3600))
    body: dict[str, Any] = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "field_set": "minimal" if minimal else "full",
        "scan_interval_seconds": interval,
        "coins": coins_out,
    }
    body.update(_optional_scan_health_fields(scan_health))
    if regime_gate:
        body["regime_gate"] = regime_gate
    if api_cost_panel:
        body["api_cost_panel"] = api_cost_panel
    if notify_public_config:
        body["notify_public_config"] = notify_public_config
    qe = _public_qualification_exits(qualification_exits)
    if qe:
        body["qualification_exits"] = qe
    body["snapshot_validation"] = validate_public_snapshot(body)
    return body


def write_public_qualified_snapshot(
    data_dir: Path,
    filename: str,
    final_results: list[dict[str, Any]],
    *,
    field_set: str = "full",
    scan_interval_seconds: int = 3600,
    scan_health: dict[str, Any] | None = None,
    regime_gate: dict[str, Any] | None = None,
    api_cost_panel: dict[str, Any] | None = None,
    qualification_exits: list[dict[str, Any]] | None = None,
    notify_public_config: dict[str, Any] | None = None,
) -> None:
    payload = build_public_qualified_snapshot(
        final_results,
        field_set=field_set,
        scan_interval_seconds=scan_interval_seconds,
        scan_health=scan_health,
        regime_gate=regime_gate,
        api_cost_panel=api_cost_panel,
        qualification_exits=qualification_exits,
        notify_public_config=notify_public_config,
    )
    _atomic_write_json(data_dir / filename, payload)
