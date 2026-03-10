"""Parallel backtesting runner for scanner integration (Sprint 4.1)."""

from __future__ import annotations

import json
import time
from collections import Counter
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


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _classify_failure(reason: str) -> str:
    normalized = str(reason or "unknown").lower()
    if normalized.startswith("optimize_error"):
        return "optimizer_error"
    if normalized in {"load_failed", "insufficient_history", "no_market_data"}:
        return "data_unavailable"
    if "pickle" in normalized or "brokenprocesspool" in normalized:
        return "worker_pool_error"
    if "timeout" in normalized:
        return "timeout"
    if "mapping" in normalized:
        return "mapping_error"
    return "other"


def _telemetry_event(event_type: str, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "timestamp": _iso_now(),
        "event": event_type,
    }
    payload.update(fields)
    return payload


def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _log_progress(
    total: int,
    completed: int,
    failed: int,
    symbol: str,
    status: str,
    rows: int,
    skipped: int,
    started_at: float,
) -> None:
    elapsed = max(0.0, time.monotonic() - started_at)
    rate = completed / elapsed if elapsed > 0 else 0.0
    remaining = max(0, total - completed)
    eta_seconds = (remaining / rate) if rate > 0 else 0.0
    print(
        "[BACKTEST] "
        f"{completed}/{total} | failed={failed} | {status} {symbol} "
        f"| rows={rows} skipped={skipped} "
        f"| elapsed={_fmt_duration(elapsed)} eta={_fmt_duration(eta_seconds)} "
        f"rate={rate:.2f} coin/s",
        flush=True,
    )


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_checkpoint(
    checkpoint_path: Path,
    eligible_symbols: list[str],
    completed_symbols: list[str],
    coins_processed: int,
    coins_failed: int,
    failure_breakdown: dict[str, int],
    results: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    payload = {
        "updated_at": _iso_now(),
        "eligible_symbols": eligible_symbols,
        "completed_symbols": sorted(set(completed_symbols)),
        "coins_processed": int(coins_processed),
        "coins_failed": int(coins_failed),
        "failure_breakdown": dict(failure_breakdown),
        "results": results,
        "skipped": skipped,
        "failures": failures,
    }
    _write_json(checkpoint_path, payload)


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

    checkpoint_path = settings.backtest_checkpoint_file
    telemetry_path = settings.backtest_telemetry_file

    timeframes = settings.backtest_timeframes
    max_failure_samples = int(settings.backtest_failure_samples_limit)

    summary: dict[str, Any] = {
        "generated_at": _iso_now(),
        "backtest_enabled": settings.backtest_enabled,
        "exchange_gate_enabled": exchange_gate_enabled,
        "target_exchanges": sorted(target_exchanges),
        "timeframes": timeframes,
        "resume_enabled": settings.backtest_resume_enabled,
        "checkpoint_file": str(checkpoint_path),
        "telemetry_file": str(telemetry_path),
        "coins_considered": len(final_results),
        "coins_eligible": len(eligible_coins),
        "coins_processed": 0,
        "coins_failed": 0,
        "rows_generated": 0,
        "resumed_from_checkpoint": False,
        "resumed_completed_symbols": 0,
        "failure_breakdown": {},
        "failures": [],
        "skipped": preflight_skipped,
        "results": [],
    }

    _append_jsonl(
        telemetry_path,
        _telemetry_event(
            "run_start",
            eligible=len(eligible_coins),
            considered=len(final_results),
            worker_cap=settings.backtest_parallel_workers,
            timeframes=timeframes,
        ),
    )

    if preflight_skipped:
        for row in preflight_skipped:
            _append_jsonl(
                telemetry_path,
                _telemetry_event(
                    "coin_preflight_skipped",
                    symbol=row.get("symbol"),
                    reason=row.get("reason"),
                    class_name=_classify_failure(str(row.get("reason", ""))),
                ),
            )

    if not eligible_coins:
        _write_json(output_path, summary)
        _append_jsonl(telemetry_path, _telemetry_event("run_complete", **{
            "processed": 0,
            "failed": 0,
            "rows": 0,
        }))
        return summary

    eligible_symbols = [coin["symbol"] for coin in eligible_coins]
    resumed_symbols: set[str] = set()
    completed_symbols: list[str] = []
    failure_counter: Counter[str] = Counter()

    if settings.backtest_resume_enabled:
        checkpoint = _load_checkpoint(checkpoint_path)
        if checkpoint:
            prior_eligible = {
                str(symbol).upper()
                for symbol in checkpoint.get("eligible_symbols", [])
            }
            if prior_eligible == set(eligible_symbols):
                resumed_symbols = {
                    str(symbol).upper()
                    for symbol in checkpoint.get("completed_symbols", [])
                }
                summary["coins_processed"] = int(checkpoint.get("coins_processed", 0))
                summary["coins_failed"] = int(checkpoint.get("coins_failed", 0))
                summary["results"] = list(checkpoint.get("results", []))
                summary["skipped"].extend(list(checkpoint.get("skipped", [])))
                summary["failures"].extend(list(checkpoint.get("failures", [])))
                existing_breakdown = checkpoint.get("failure_breakdown", {})
                if isinstance(existing_breakdown, dict):
                    for key, count in existing_breakdown.items():
                        failure_counter[str(key)] += int(count)
                if not failure_counter:
                    for item in summary["failures"]:
                        failure_counter[_classify_failure(str(item.get("reason", "")))] += 1
                summary["resumed_from_checkpoint"] = True
                summary["resumed_completed_symbols"] = len(resumed_symbols)
                _append_jsonl(
                    telemetry_path,
                    _telemetry_event(
                        "resume_loaded",
                        resumed=len(resumed_symbols),
                        prior_rows=len(summary["results"]),
                    ),
                )
            else:
                _append_jsonl(
                    telemetry_path,
                    _telemetry_event(
                        "resume_discarded",
                        reason="eligible_set_changed",
                        previous_eligible=len(prior_eligible),
                        current_eligible=len(eligible_symbols),
                    ),
                )

    pending_coins = [coin for coin in eligible_coins if coin["symbol"] not in resumed_symbols]
    completed_symbols.extend(sorted(resumed_symbols))

    worker_count = max(1, min(settings.backtest_parallel_workers, len(pending_coins)))

    expected_runs_per_coin = (
        len(timeframes) * (1 + (len(SIGNAL_REGISTRY) * int(settings.backtest_max_param_combos) * 21))
    )
    print(
        "[BACKTEST] "
        f"starting run | eligible={len(eligible_symbols)} pending={len(pending_coins)} "
        f"workers={worker_count} timeframes={timeframes} indicators={len(SIGNAL_REGISTRY)} "
        f"max_param_combos={int(settings.backtest_max_param_combos)} "
        f"est_max_runs_per_coin={expected_runs_per_coin}",
        flush=True,
    )
    if resumed_symbols:
        print(
            "[BACKTEST] "
            f"resume detected | resumed_symbols={len(resumed_symbols)}",
            flush=True,
        )

    if not pending_coins:
        if summary["coins_processed"] == 0 and summary["coins_failed"] == 0:
            summary["coins_processed"] = len(eligible_symbols) - len(summary["failures"])
            summary["coins_failed"] = len(summary["failures"])
        summary["rows_generated"] = len(summary["results"])
        summary["failure_breakdown"] = dict(failure_counter)
        _write_json(output_path, summary)
        _append_jsonl(
            telemetry_path,
            _telemetry_event(
                "run_complete",
                processed=summary["coins_processed"],
                failed=summary["coins_failed"],
                rows=summary["rows_generated"],
                resumed_only=True,
            ),
        )
        return summary

    if worker_count == 1:
        progress_started_at = time.monotonic()
        total_to_process = len(pending_coins)
        completed_count = 0
        for index, coin in enumerate(pending_coins, start=1):
            symbol = coin["symbol"]
            print(
                "[BACKTEST] "
                f"starting {index}/{total_to_process} | symbol={symbol} | mode=single-worker",
                flush=True,
            )
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
                skipped_reason_counts = Counter(
                    str(item.get("reason", "unknown"))
                    for item in result.get("skipped", [])
                )
                completed_symbols.append(symbol)
                completed_count += 1
                _log_progress(
                    total=total_to_process,
                    completed=completed_count,
                    failed=summary["coins_failed"],
                    symbol=symbol,
                    status="ok",
                    rows=len(result.get("rows", [])),
                    skipped=len(result.get("skipped", [])),
                    started_at=progress_started_at,
                )
                _append_jsonl(
                    telemetry_path,
                    _telemetry_event(
                        "coin_processed",
                        symbol=symbol,
                        rows=len(result.get("rows", [])),
                        skipped=len(result.get("skipped", [])),
                        skipped_reason_counts=dict(skipped_reason_counts),
                    ),
                )
                _save_checkpoint(
                    checkpoint_path,
                    eligible_symbols,
                    completed_symbols,
                    summary["coins_processed"],
                    summary["coins_failed"],
                    dict(failure_counter),
                    summary["results"],
                    summary["skipped"],
                    summary["failures"],
                )
            except Exception as exc:
                summary["coins_failed"] += 1
                reason = str(exc)
                class_name = _classify_failure(reason)
                failure_counter[class_name] += 1
                if len(summary["failures"]) < max_failure_samples:
                    summary["failures"].append({"symbol": symbol, "reason": reason, "class_name": class_name})
                completed_symbols.append(symbol)
                completed_count += 1
                _log_progress(
                    total=total_to_process,
                    completed=completed_count,
                    failed=summary["coins_failed"],
                    symbol=symbol,
                    status="failed",
                    rows=0,
                    skipped=0,
                    started_at=progress_started_at,
                )
                _append_jsonl(
                    telemetry_path,
                    _telemetry_event(
                        "coin_failed",
                        symbol=symbol,
                        reason=reason,
                        class_name=class_name,
                    ),
                )
                _save_checkpoint(
                    checkpoint_path,
                    eligible_symbols,
                    completed_symbols,
                    summary["coins_processed"],
                    summary["coins_failed"],
                    dict(failure_counter),
                    summary["results"],
                    summary["skipped"],
                    summary["failures"],
                )
    else:
        progress_started_at = time.monotonic()
        total_to_process = len(pending_coins)
        completed_count = 0
        symbol_to_index = {
            coin["symbol"]: index
            for index, coin in enumerate(pending_coins, start=1)
        }
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            for coin in pending_coins:
                idx = symbol_to_index[coin["symbol"]]
                print(
                    "[BACKTEST] "
                    f"queued {idx}/{total_to_process} | symbol={coin['symbol']} | mode=parallel",
                    flush=True,
                )
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
                for coin in pending_coins
            }
            print(
                "[BACKTEST] "
                f"submitted {len(future_map)} coins to worker pool",
                flush=True,
            )

            for future in as_completed(future_map):
                symbol = future_map[future]
                idx = symbol_to_index.get(symbol, 0)
                try:
                    result = future.result()
                    summary["coins_processed"] += 1
                    summary["results"].extend(result.get("rows", []))
                    summary["skipped"].extend(result.get("skipped", []))
                    skipped_reason_counts = Counter(
                        str(item.get("reason", "unknown"))
                        for item in result.get("skipped", [])
                    )
                    completed_symbols.append(symbol)
                    completed_count += 1
                    _log_progress(
                        total=total_to_process,
                        completed=completed_count,
                        failed=summary["coins_failed"],
                        symbol=symbol,
                        status="ok",
                        rows=len(result.get("rows", [])),
                        skipped=len(result.get("skipped", [])),
                        started_at=progress_started_at,
                    )
                    _append_jsonl(
                        telemetry_path,
                        _telemetry_event(
                            "coin_processed",
                            symbol=symbol,
                            queue_index=idx,
                            rows=len(result.get("rows", [])),
                            skipped=len(result.get("skipped", [])),
                            skipped_reason_counts=dict(skipped_reason_counts),
                        ),
                    )
                    _save_checkpoint(
                        checkpoint_path,
                        eligible_symbols,
                        completed_symbols,
                        summary["coins_processed"],
                        summary["coins_failed"],
                        dict(failure_counter),
                        summary["results"],
                        summary["skipped"],
                        summary["failures"],
                    )
                except Exception as exc:
                    summary["coins_failed"] += 1
                    reason = str(exc)
                    class_name = _classify_failure(reason)
                    failure_counter[class_name] += 1
                    if len(summary["failures"]) < max_failure_samples:
                        summary["failures"].append({"symbol": symbol, "reason": reason, "class_name": class_name})
                    completed_symbols.append(symbol)
                    completed_count += 1
                    _log_progress(
                        total=total_to_process,
                        completed=completed_count,
                        failed=summary["coins_failed"],
                        symbol=symbol,
                        status="failed",
                        rows=0,
                        skipped=0,
                        started_at=progress_started_at,
                    )
                    _append_jsonl(
                        telemetry_path,
                        _telemetry_event(
                            "coin_failed",
                            symbol=symbol,
                            queue_index=idx,
                            reason=reason,
                            class_name=class_name,
                        ),
                    )
                    _save_checkpoint(
                        checkpoint_path,
                        eligible_symbols,
                        completed_symbols,
                        summary["coins_processed"],
                        summary["coins_failed"],
                        dict(failure_counter),
                        summary["results"],
                        summary["skipped"],
                        summary["failures"],
                    )

    summary["rows_generated"] = len(summary["results"])
    summary["failure_breakdown"] = dict(failure_counter)

    _write_json(output_path, summary)
    print(
        "[BACKTEST] "
        f"complete | processed={summary['coins_processed']} failed={summary['coins_failed']} "
        f"rows={summary['rows_generated']}",
        flush=True,
    )
    _append_jsonl(
        telemetry_path,
        _telemetry_event(
            "run_complete",
            processed=summary["coins_processed"],
            failed=summary["coins_failed"],
            rows=summary["rows_generated"],
            resumed=summary["resumed_completed_symbols"],
        ),
    )
    return summary
