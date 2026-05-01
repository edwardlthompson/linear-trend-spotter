"""Optional alert backtesting report artifact (Milestone O3)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pnl_pct(entry_price: float, last_price: float) -> float | None:
    try:
        ep = float(entry_price)
        lp = float(last_price)
    except Exception:
        return None
    if ep <= 0 or lp <= 0:
        return None
    return round(((lp - ep) / ep) * 100.0, 2)


def write_alert_backtest_report(
    *,
    path: Path,
    final_results: list[dict[str, Any]],
    active_after_update: dict[str, dict[str, Any]],
    exited: list[dict[str, Any]],
    top_n: int,
) -> dict[str, Any]:
    top_rows: list[dict[str, Any]] = []
    for coin in final_results[: max(1, int(top_n))]:
        sym = str(coin.get("symbol", "")).upper()
        if not sym:
            continue
        state = active_after_update.get(sym, {})
        entry_price = float(state.get("entry_price") or 0.0)
        last_price = float(state.get("last_price") or coin.get("current_price") or 0.0)
        top_rows.append(
            {
                "symbol": sym,
                "current_rank": coin.get("current_rank"),
                "health_score": coin.get("health_score"),
                "uniformity_score": coin.get("uniformity_score"),
                "entry_price": entry_price if entry_price > 0 else None,
                "last_price": last_price if last_price > 0 else None,
                "hypothetical_pnl_pct": _pnl_pct(entry_price, last_price),
            }
        )

    exit_rows = []
    for item in exited[: max(1, int(top_n))]:
        exit_rows.append(
            {
                "symbol": str(item.get("symbol", "")).upper(),
                "exit_reason": str(item.get("exit_reason", "")),
                "lifecycle_pnl_pct": item.get("lifecycle_pnl_pct"),
                "lifecycle_max_runup_pct": item.get("lifecycle_max_runup_pct"),
                "lifecycle_max_drawdown_pct": item.get("lifecycle_max_drawdown_pct"),
                "held_days": item.get("lifecycle_held_days"),
            }
        )

    payload = {
        "updated_at": _iso_now(),
        "top_n": max(1, int(top_n)),
        "top_alerts_hypothetical": top_rows,
        "recent_exits": exit_rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
