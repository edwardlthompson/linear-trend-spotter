"""Optional multi-portfolio simulation artifact writer (Milestone O1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_multi_portfolio_simulation(
    *,
    path: Path,
    insights_payload: dict[str, Any],
    capitals: list[float],
) -> dict[str, Any]:
    sim = insights_payload.get("portfolio_simulation", {}) if isinstance(insights_payload, dict) else {}
    start = float(sim.get("starting_capital", 0.0) or 0.0)
    equity = float(sim.get("equity", 0.0) or 0.0)
    if start <= 0:
        growth_factor = 1.0
    else:
        growth_factor = equity / start

    portfolios = []
    for capital in capitals:
        c = float(capital)
        eq = round(c * growth_factor, 2)
        pnl_abs = round(eq - c, 2)
        pnl_pct = round(((eq / c) - 1.0) * 100.0, 2) if c > 0 else 0.0
        portfolios.append(
            {
                "starting_capital": round(c, 2),
                "equity": eq,
                "pnl_abs": pnl_abs,
                "pnl_pct": pnl_pct,
            }
        )

    payload = {
        "updated_at": _iso_now(),
        "source": "scanner_insights.portfolio_simulation",
        "growth_factor": round(growth_factor, 6),
        "portfolios": portfolios,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
