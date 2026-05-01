"""Active ranking rows for event summary (extracted from main.py, Milestone I2)."""

from __future__ import annotations

from datetime import datetime, timezone


def _pct_change(current_value: float, baseline_value: float) -> float | None:
    try:
        current = float(current_value)
        baseline = float(baseline_value)
    except Exception:
        return None
    if baseline <= 0:
        return None
    return ((current - baseline) / baseline) * 100.0


def _format_time_on_list(entered_date_raw: str | None) -> str:
    entered_date = str(entered_date_raw or "").strip()
    if not entered_date:
        return "n/a"
    try:
        entered_at = datetime.fromisoformat(entered_date.replace("Z", "+00:00"))
    except Exception:
        return "n/a"

    if entered_at.tzinfo is None:
        entered_at = entered_at.replace(tzinfo=timezone.utc)

    elapsed = datetime.now(timezone.utc) - entered_at.astimezone(timezone.utc)
    if elapsed.total_seconds() < 0:
        return "n/a"

    total_hours = int(elapsed.total_seconds() // 3600)
    days = total_hours // 24
    hours = total_hours % 24
    if days > 0:
        return f"{days}d {hours}h"
    return f"{hours}h"


def build_active_ranking_rows(
    final_results: list[dict],
    active_after_update: dict[str, dict],
) -> list[dict]:
    rows: list[dict] = []
    active_symbols = set(active_after_update.keys())

    active_rank = 0
    for coin in final_results:
        symbol = str(coin.get("symbol", "")).upper()
        if not symbol or symbol not in active_symbols:
            continue
        active_rank += 1

        after_state = active_after_update.get(symbol, {})
        current_price = float(coin.get("current_price", 0.0) or 0.0)
        gain_since_entry_pct = _pct_change(current_price, float(after_state.get("entry_price", 0.0) or 0.0))
        time_on_list = _format_time_on_list(after_state.get("entered_date"))

        rows.append(
            {
                "symbol": symbol,
                "active_rank": active_rank,
                "current_rank": coin.get("current_rank"),
                "rank_status": coin.get("rank_status"),
                "rank_delta": coin.get("rank_delta"),
                "health_score": coin.get("health_score"),
                "gain_since_entry_pct": gain_since_entry_pct,
                "time_on_list": time_on_list,
            }
        )

    return rows
