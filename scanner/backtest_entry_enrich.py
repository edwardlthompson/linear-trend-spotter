"""Attach current-run backtest rows to newly entered coins."""

from __future__ import annotations

from typing import Any

from backtesting.report import notification_rows_for_symbol


def enrich_entered_with_current_backtest(
    entered: list[dict[str, Any]],
    final_results: list[dict[str, Any]],
    backtest_summary: dict[str, Any] | None,
) -> None:
    """Mutate entered coins with strategy rows from *this* scan's summary only.

    Never loads ``backtest_results.json`` from disk. A prior artifact would attach
    stale Bot/B&H percentages into the public snapshot and entry alerts when the
    current run skipped or failed backtests (``entered`` shares dict identity
    with ``final_results``).
    """
    if not entered or not backtest_summary:
        return

    by_symbol = {
        str(coin.get("symbol", "")).upper(): coin
        for coin in final_results
        if coin.get("symbol")
    }
    for coin in entered:
        symbol = str(coin.get("symbol", "")).upper()
        if not symbol:
            continue
        enriched = by_symbol.get(symbol)
        if enriched is not None and enriched is not coin:
            coin.update(enriched)
        if coin.get("backtest_top_strategies") and coin.get("backtest_buy_hold"):
            continue
        details = notification_rows_for_symbol(backtest_summary, symbol, top_n=5)
        coin["backtest_top_strategies"] = details.get("top_strategies", [])
        coin["backtest_buy_hold"] = details.get("buy_hold")
