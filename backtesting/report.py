"""Backtesting report utilities and final output contract rendering."""

from __future__ import annotations

import math
from typing import Any
from typing import List

from tabulate import tabulate

REQUIRED_COLUMNS = [
    "Indicator",
    "TF",
    "Key Settings",
    "Stop Loss %",
    "Final $",
    "Net %",
    "Trades",
    "Win %",
]


def _ensure_finite(value: float, name: str) -> None:
    if value is None or not math.isfinite(float(value)):
        raise ValueError(f"Invalid numeric value for {name}: {value}")


def _format_money(value: float) -> str:
    return f"${float(value):,.2f}"


def _format_pct(value: float) -> str:
    return f"{float(value):.2f}%"


def _format_settings(params: dict[str, Any] | None) -> str:
    if not params:
        return "none"
    parts = []
    for key in sorted(params.keys()):
        parts.append(f"{key}={params[key]}")
    return ", ".join(parts)


def validate_ranked_rows(rows: List[dict]) -> None:
    if not rows:
        raise ValueError("Ranked rows are empty")

    for row in rows:
        for col in REQUIRED_COLUMNS:
            if col not in row:
                raise ValueError(f"Missing required report column: {col}")

        _ensure_finite(row["_net_value"], "_net_value")

        if row["Indicator"] != "B&H":
            _ensure_finite(row["_final_value"], "_final_value")
            if row["Trades"] == "-":
                raise ValueError("Strategy row cannot have '-' trades")
            if row["Win %"] == "-":
                raise ValueError("Strategy row cannot have '-' win %")


def sort_rows(rows: List[dict]) -> List[dict]:
    validate_ranked_rows(rows)
    return sorted(rows, key=lambda item: item["_net_value"], reverse=True)


def render_ranked_table(rows: List[dict]) -> str:
    sorted_rows = sort_rows(rows)
    printable = []

    for row in sorted_rows:
        printable.append({k: row[k] for k in REQUIRED_COLUMNS})

    return tabulate(printable, headers="keys", tablefmt="github", floatfmt=".2f")


def rows_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in summary.get("results", []):
        indicator = str(item.get("indicator", "Unknown"))
        net_pct = float(item.get("net_pct", 0.0))
        final_equity = float(item.get("final_equity", 0.0))

        is_buy_hold = indicator == "B&H"
        trailing_stop = item.get("trailing_stop_pct")

        row = {
            "Indicator": indicator,
            "TF": str(item.get("timeframe", "")),
            "Key Settings": _format_settings(item.get("params", {})),
            "Stop Loss %": "-" if is_buy_hold else _format_pct(float(trailing_stop or 0.0)),
            "Final $": _format_money(final_equity),
            "Net %": _format_pct(net_pct),
            "Trades": "-" if is_buy_hold else int(item.get("trades", 0)),
            "Win %": "-" if is_buy_hold else _format_pct(float(item.get("win_pct", 0.0))),
            "_net_value": net_pct,
            "_final_value": final_equity,
            "_raw": item,
        }
        rows.append(row)

    return rows


def top_settings_block(summary: dict[str, Any]) -> str:
    rows = rows_from_summary(summary)
    ranked = sort_rows(rows)

    best_strategy_row = None
    for row in ranked:
        if row["Indicator"] != "B&H":
            best_strategy_row = row
            break

    if best_strategy_row is None:
        return "#1 Settings: no strategy result available"

    raw = best_strategy_row["_raw"]
    params = raw.get("params", {}) or {}
    stop = raw.get("trailing_stop_pct", 0.0)
    settings_text = _format_settings(params)
    return (
        "#1 Settings: "
        f"indicator={raw.get('indicator')}, "
        f"tf={raw.get('timeframe')}, "
        f"params=[{settings_text}], "
        f"trailing_stop={float(stop):.0f}%, "
        f"net={float(raw.get('net_pct', 0.0)):.2f}%"
    )


def notification_rows_for_symbol(summary: dict[str, Any], symbol: str, top_n: int = 5) -> dict[str, Any]:
    """Return top strategy rows and separate B&H row for one symbol."""
    symbol_key = symbol.upper()
    result_rows = [row for row in summary.get("results", []) if str(row.get("symbol", "")).upper() == symbol_key]

    if not result_rows:
        return {"top_strategies": [], "buy_hold": None}

    strategy_rows = [row for row in result_rows if str(row.get("indicator", "")) != "B&H"]
    strategy_rows_sorted = sorted(strategy_rows, key=lambda item: float(item.get("net_pct", float("-inf"))), reverse=True)

    buy_hold_rows = [row for row in result_rows if str(row.get("indicator", "")) == "B&H"]
    buy_hold_best = None
    if buy_hold_rows:
        buy_hold_best = sorted(buy_hold_rows, key=lambda item: float(item.get("net_pct", float("-inf"))), reverse=True)[0]

    return {
        "top_strategies": strategy_rows_sorted[:max(0, top_n)],
        "buy_hold": buy_hold_best,
    }
