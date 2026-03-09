"""Parallel backtesting runner for scanner integration (Sprint 4.1)."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from database.cache import PriceCache

from .data_loader import BacktestDataLoader
from .engine import compute_buy_and_hold
from .models import BacktestConfig
from .optimizer import optimize_indicator
from .signals import SIGNAL_REGISTRY


def _optimize_coin_task(
    symbol: str,
    gecko_id: str | None,
    timeframes: list[str],
    db_path: str,
    cache_age_hours: int,
    max_param_combos: int,
    starting_capital: float,
    fee_bps_round_trip: float,
) -> dict[str, Any]:
    cache = PriceCache(Path(db_path))
    loader = BacktestDataLoader(cache=cache, max_cache_age_hours=cache_age_hours)

    strategy_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    try:
        for timeframe in timeframes:
            loaded = loader.load(symbol=symbol, timeframe=timeframe, days=30, gecko_id=gecko_id)
            if loaded.frame is None:
                skipped.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "reason": loaded.skip_reason or "load_failed",
                })
                continue

            buy_hold = compute_buy_and_hold(
                loaded.frame,
                BacktestConfig(
                    starting_capital=starting_capital,
                    fee_bps_round_trip=fee_bps_round_trip,
                    trailing_stop_pct=0.0,
                ),
            )
            strategy_rows.append(
                {
                    "indicator": "B&H",
                    "timeframe": timeframe,
                    "params": {},
                    "trailing_stop_pct": None,
                    "final_equity": float(buy_hold.final_equity),
                    "net_pct": float(buy_hold.net_pct),
                    "trades": "-",
                    "win_pct": "-",
                    "symbol": symbol,
                    "combos_evaluated": 1,
                    "stops_tested": 0,
                    "total_runs": 1,
                    "skipped_combos": 0,
                }
            )

            for indicator in SIGNAL_REGISTRY.keys():
                try:
                    summary = optimize_indicator(
                        frame=loaded.frame,
                        indicator=indicator,
                        timeframe=timeframe,
                        max_param_combos=max_param_combos,
                        starting_capital=starting_capital,
                        fee_bps_round_trip=fee_bps_round_trip,
                    )
                except Exception as exc:
                    skipped.append(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "indicator": indicator,
                            "reason": f"optimize_error:{exc}",
                        }
                    )
                    continue

                if summary.best_result is None:
                    skipped.append(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "indicator": indicator,
                            "reason": "no_best_result",
                        }
                    )
                    continue

                row = dict(summary.best_result)
                row["symbol"] = symbol
                row["combos_evaluated"] = summary.combos_evaluated
                row["stops_tested"] = summary.stops_tested
                row["total_runs"] = summary.total_runs
                row["skipped_combos"] = summary.skipped_combos
                strategy_rows.append(row)

        return {
            "symbol": symbol,
            "ok": True,
            "rows": strategy_rows,
            "skipped": skipped,
        }
    finally:
        cache.close()


def run_backtests_for_final_results(final_results: list[dict], output_path: Path | None = None) -> dict[str, Any]:
    """Run optimizer for final-stage coins and persist JSON artifact.

    Default behavior backtests all final-stage coins. Optional exchange gating is
    controlled by BACKTEST_REQUIRE_TARGET_EXCHANGE with BACKTEST_EXCHANGES.
    """
    target_exchanges = {
        str(exchange).strip().lower()
        for exchange in settings.backtest_exchanges
        if str(exchange).strip()
    }
    exchange_gate_enabled = settings.backtest_require_target_exchange

    eligible = []
    preflight_skipped: list[dict[str, Any]] = []
    for coin in final_results:
        raw_listed_on = coin.get("listed_on", [])
        if isinstance(raw_listed_on, str):
            listed_on = {raw_listed_on.strip().lower()} if raw_listed_on.strip() else set()
        else:
            listed_on = {
                str(exchange).strip().lower()
                for exchange in raw_listed_on
                if str(exchange).strip()
            }

        if not exchange_gate_enabled:
            eligible.append(coin)
        elif not target_exchanges:
            preflight_skipped.append(
                {
                    "symbol": str(coin.get("symbol", "")).upper(),
                    "timeframe": None,
                    "reason": "no_target_exchanges_configured",
                    "listed_on": sorted(listed_on),
                    "target_exchanges": [],
                }
            )
        elif listed_on.intersection(target_exchanges):
            eligible.append(coin)
        else:
            preflight_skipped.append(
                {
                    "symbol": str(coin.get("symbol", "")).upper(),
                    "timeframe": None,
                    "reason": "not_on_target_exchange",
                    "listed_on": sorted(listed_on),
                    "target_exchanges": sorted(target_exchanges),
                }
            )

    max_coins = settings.backtest_max_coins_per_run
    if max_coins > 0:
        eligible = eligible[:max_coins]

    eligible_coins = []
    for coin in eligible:
        symbol = str(coin.get("symbol", "")).upper()
        if not symbol:
            continue
        gecko_id = coin.get("gecko_id") or coin.get("cg_id")
        eligible_coins.append({"symbol": symbol, "gecko_id": gecko_id})

    if output_path is None:
        output_path = settings.base_dir / "backtest_results.json"

    timeframes = settings.backtest_timeframes

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backtest_enabled": settings.backtest_enabled,
        "exchange_gate_enabled": exchange_gate_enabled,
        "target_exchanges": sorted(target_exchanges),
        "timeframes": timeframes,
        "coins_considered": len(final_results),
        "coins_eligible": len(eligible_coins),
        "coins_processed": 0,
        "coins_failed": 0,
        "rows_generated": 0,
        "failures": [],
        "skipped": preflight_skipped,
        "results": [],
    }

    if not eligible_coins:
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    worker_count = max(1, min(settings.backtest_parallel_workers, len(eligible_coins)))

    if worker_count == 1:
        for coin in eligible_coins:
            symbol = coin["symbol"]
            try:
                result = _optimize_coin_task(
                    symbol,
                    coin.get("gecko_id"),
                    timeframes,
                    str(settings.db_paths["scanner"]),
                    int(settings.cache_price_hours),
                    int(settings.backtest_max_param_combos),
                    float(settings.backtest_starting_capital),
                    float(settings.backtest_fee_bps_round_trip),
                )
                summary["coins_processed"] += 1
                summary["results"].extend(result.get("rows", []))
                summary["skipped"].extend(result.get("skipped", []))
            except Exception as exc:
                summary["coins_failed"] += 1
                summary["failures"].append({"symbol": symbol, "reason": str(exc)})
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(
                    _optimize_coin_task,
                    coin["symbol"],
                    coin.get("gecko_id"),
                    timeframes,
                    str(settings.db_paths["scanner"]),
                    int(settings.cache_price_hours),
                    int(settings.backtest_max_param_combos),
                    float(settings.backtest_starting_capital),
                    float(settings.backtest_fee_bps_round_trip),
                ): coin["symbol"]
                for coin in eligible_coins
            }

            for future in as_completed(future_map):
                symbol = future_map[future]
                try:
                    result = future.result()
                    summary["coins_processed"] += 1
                    summary["results"].extend(result.get("rows", []))
                    summary["skipped"].extend(result.get("skipped", []))
                except Exception as exc:
                    summary["coins_failed"] += 1
                    summary["failures"].append({"symbol": symbol, "reason": str(exc)})

    summary["rows_generated"] = len(summary["results"])

    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
