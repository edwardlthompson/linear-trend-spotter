"""Selection helpers for optimization results."""

from __future__ import annotations


def select_best_result(results: list[dict]) -> dict | None:
    if not results:
        return None

    return sorted(
        results,
        key=lambda row: (
            float(row.get("net_pct", float("-inf"))),
            float(row.get("final_equity", float("-inf"))),
            -int(row.get("trades", 0)),
        ),
        reverse=True,
    )[0]
