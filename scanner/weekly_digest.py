"""Weekly digest state and message helpers (extracted from main.py, Milestone I2)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import settings


def load_weekly_digest_state() -> dict[str, Any]:
    path = settings.weekly_digest_state_file
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_weekly_digest_state(payload: dict[str, Any]) -> None:
    path = settings.weekly_digest_state_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def iso_week_key(moment: datetime) -> str:
    iso_year, iso_week, _ = moment.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def build_weekly_digest_message(history_db: Any, active_db: Any) -> str:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=7)
    cutoff_iso = cutoff.isoformat()
    cutoff_date = cutoff.date().isoformat()

    scans_cursor = history_db.execute(
        "SELECT COUNT(DISTINCT scan_date) FROM scan_history WHERE scan_date >= ?",
        (cutoff_iso,),
    )
    scans_count = int((scans_cursor.fetchone() or [0])[0] or 0)

    symbol_cursor = history_db.execute(
        "SELECT COUNT(DISTINCT coin_symbol) FROM scan_history WHERE scan_date >= ?",
        (cutoff_iso,),
    )
    unique_symbols = int((symbol_cursor.fetchone() or [0])[0] or 0)

    score_cursor = history_db.execute(
        "SELECT AVG(uniformity_score), MAX(uniformity_score) FROM scan_history WHERE scan_date >= ?",
        (cutoff_iso,),
    )
    score_row = score_cursor.fetchone() or [0, 0]
    avg_score = float(score_row[0] or 0.0)
    best_score = float(score_row[1] or 0.0)

    top_cursor = history_db.execute(
        """
        SELECT coin_symbol, COUNT(*) AS appearances
        FROM scan_history
        WHERE scan_date >= ?
        GROUP BY coin_symbol
        ORDER BY appearances DESC, coin_symbol ASC
        LIMIT 5
        """,
        (cutoff_iso,),
    )
    top_symbols = top_cursor.fetchall()

    active_entries_cursor = active_db.execute(
        "SELECT COUNT(*) FROM active_coins WHERE entered_date >= ?",
        (cutoff_date,),
    )
    new_entries_week = int((active_entries_cursor.fetchone() or [0])[0] or 0)

    recent_exits = active_db.get_recent_exits(days=7)
    exit_count = len(recent_exits)
    active_count = len(active_db.get_active())

    lines = [
        "📅 <b>Weekly Performance Digest</b>",
        "Window: last 7 days (UTC)",
        f"Scans run: {scans_count}",
        f"Unique qualified symbols: {unique_symbols}",
        f"Average uniformity: {avg_score:.1f}",
        f"Best uniformity: {best_score:.1f}",
        f"New entries (active this week): {new_entries_week}",
        f"Exits: {exit_count}",
        f"Currently active: {active_count}",
    ]

    if top_symbols:
        lines.append("Top recurring symbols:")
        for symbol, appearances in top_symbols:
            lines.append(f"• {symbol}: {appearances} appearances")

    return "\n".join(lines)
