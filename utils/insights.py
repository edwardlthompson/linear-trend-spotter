"""Scanner insights, dashboards, and lightweight analytics artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, float(value)))


def _load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default or {})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def compute_data_reliability(coin: dict[str, Any]) -> dict[str, Any]:
    score = 0.0

    if coin.get("gecko_id") or coin.get("cg_id"):
        score += 20.0

    exchange_volumes = coin.get("exchange_volumes") or {}
    targets = max(1, len(exchange_volumes))
    populated = sum(
        1
        for value in exchange_volumes.values()
        if isinstance(value, (int, float)) and float(value) > 0
    )
    score += (populated / targets) * 20.0

    ohlcv_source = str(coin.get("ohlcv_source") or "none").lower()
    if ohlcv_source.startswith("coingecko"):
        score += 25.0
    elif ohlcv_source.startswith("polygon"):
        score += 18.0
    elif ohlcv_source == "price_cache":
        score += 20.0

    quality_candles = int(coin.get("quality_candles") or 0)
    score += min(quality_candles / 720.0, 1.0) * 20.0

    if float(coin.get("current_price", 0.0) or 0.0) > 0:
        score += 10.0
    if coin.get("source_url") or coin.get("cmc_url") or coin.get("slug"):
        score += 5.0

    score = _clamp(score)
    if score >= 80:
        label = "high"
    elif score >= 60:
        label = "good"
    elif score >= 40:
        label = "mixed"
    else:
        label = "low"

    result = {
        "data_reliability_score": round(score, 2),
        "data_reliability_label": label,
    }
    coin.update(result)
    return result


def compute_reentry_quality(symbol: str, recent_exits: list[dict[str, Any]]) -> dict[str, Any]:
    symbol_upper = str(symbol or "").upper()
    matches = [item for item in recent_exits if str(item.get("symbol", "")).upper() == symbol_upper]
    count = len(matches)
    score = _clamp(100.0 - (count * 25.0))
    if count == 0:
        label = "fresh"
    elif count == 1:
        label = "re-entry"
    elif count == 2:
        label = "churn-risk"
    else:
        label = "recycled"
    return {
        "reentry_quality_score": round(score, 2),
        "reentry_quality_label": label,
        "recent_exit_count": count,
    }


def compute_health_score(coin: dict[str, Any]) -> dict[str, Any]:
    rank = coin.get("current_rank")
    rank_component = 0.0
    if isinstance(rank, int) and rank > 0:
        rank_component = max(0.0, 100.0 - ((rank - 1) * 6.0))

    uniformity = float(coin.get("uniformity_score", 0.0) or 0.0)
    reliability = float(coin.get("data_reliability_score", 0.0) or 0.0)
    volume_accel = float(coin.get("volume_acceleration_pct", 0.0) or 0.0)
    volume_component = _clamp(50.0 + (volume_accel / 4.0))

    confidence = None
    strategies = coin.get("backtest_top_strategies") or []
    if strategies:
        confidence = float(strategies[0].get("confidence_score", 50.0) or 50.0)
    confidence_component = float(confidence or 50.0)

    score = (
        (uniformity * 0.35)
        + (rank_component * 0.20)
        + (reliability * 0.25)
        + (volume_component * 0.05)
        + (confidence_component * 0.15)
    )
    score = _clamp(score)

    if score >= 80:
        label = "elite"
    elif score >= 65:
        label = "strong"
    elif score >= 50:
        label = "watch"
    else:
        label = "fragile"

    result = {
        "health_score": round(score, 2),
        "health_label": label,
    }
    coin.update(result)
    return result





def update_scanner_insights(
    path: Path,
    *,
    final_results: list[dict[str, Any]],
    all_processed: list[dict[str, Any]],
    gain_qualified: list[dict[str, Any]],
    all_cmc_coins: list[dict[str, Any]],
    entered: list[dict[str, Any]],
    exited: list[dict[str, Any]],
    active_before_update: dict[str, dict[str, Any]],
    active_after_update: dict[str, dict[str, Any]],
    blocked_by_cooldown: list[dict[str, Any]],
    current_metrics_summary: dict[str, Any],
    portfolio_starting_capital: float,
) -> dict[str, Any]:
    payload = _load_json(path, default={})
    history = list(payload.get("rank_persistence", {}).get("history", []))
    snapshot = {
        "timestamp": _iso_now(),
        "ranks": [
            {
                "symbol": str(coin.get("symbol", "")).upper(),
                "rank": coin.get("current_rank"),
                "health_score": coin.get("health_score"),
                "gain_30d": float((coin.get("gains") or {}).get("30d", 0.0) or 0.0),
            }
            for coin in final_results
        ],
    }
    history.append(snapshot)
    history = history[-100:]

    mover_totals: dict[str, int] = {}
    if len(history) >= 2:
        prev = {str(item.get("symbol", "")).upper(): int(item.get("rank") or 0) for item in history[-2].get("ranks", [])}
        for item in snapshot.get("ranks", []):
            sym = str(item.get("symbol", "")).upper()
            rank = int(item.get("rank") or 0)
            if sym in prev and prev[sym] > 0 and rank > 0:
                mover_totals[sym] = prev[sym] - rank

    active_outcomes = []
    for symbol, state in active_after_update.items():
        entry_price = float(state.get("entry_price") or 0.0)
        last_price = float(state.get("last_price") or 0.0)
        pnl = None
        if entry_price > 0 and last_price > 0:
            pnl = ((last_price - entry_price) / entry_price) * 100.0
        active_outcomes.append(
            {
                "symbol": symbol,
                "entered_date": state.get("entered_date"),
                "pnl_pct": round(float(pnl), 2) if pnl is not None else None,
            }
        )

    outcomes_summary: dict[str, Any] = {"active": len(active_outcomes), "exits_this_run": len(exited)}
    finite_outcomes = [float(item["pnl_pct"]) for item in active_outcomes if isinstance(item.get("pnl_pct"), (int, float))]
    if finite_outcomes:
        outcomes_summary["avg_active_pnl_pct"] = round(sum(finite_outcomes) / len(finite_outcomes), 2)
        outcomes_summary["median_active_pnl_pct"] = round(median(finite_outcomes), 2)
        outcomes_summary["win_rate_pct"] = round((sum(1 for item in finite_outcomes if item > 0) / len(finite_outcomes)) * 100.0, 2)

    simulation = payload.get("portfolio_simulation", {}) or {}
    cash = float(simulation.get("cash", portfolio_starting_capital) or portfolio_starting_capital)
    positions = dict(simulation.get("positions", {}))
    trades = list(simulation.get("trades", []))

    for coin in entered:
        symbol = str(coin.get("symbol", "")).upper()
        if not symbol or symbol in positions:
            continue
        current_price = float(coin.get("current_price", 0.0) or 0.0)
        if current_price <= 0 or cash <= 0:
            continue
        allocation = cash / max(1, len(entered))
        qty = allocation / current_price
        positions[symbol] = {
            "entry_price": current_price,
            "qty": qty,
            "entered_at": _iso_now(),
        }
        cash -= allocation
        trades.append({"timestamp": _iso_now(), "symbol": symbol, "side": "buy", "price": current_price, "notional": allocation})

    for coin in exited:
        symbol = str(coin.get("symbol", "")).upper()
        if symbol not in positions:
            continue
        state_before = active_before_update.get(symbol, {})
        exit_price = float(state_before.get("last_price") or 0.0)
        position = positions.pop(symbol)
        proceeds = float(position.get("qty", 0.0) or 0.0) * exit_price
        cash += proceeds
        trades.append({"timestamp": _iso_now(), "symbol": symbol, "side": "sell", "price": exit_price, "notional": proceeds})

    mark_to_market = cash
    for symbol, position in positions.items():
        state = active_after_update.get(symbol, {})
        last_price = float(state.get("last_price") or position.get("entry_price") or 0.0)
        mark_to_market += float(position.get("qty", 0.0) or 0.0) * last_price



    top_movers = sorted(mover_totals.items(), key=lambda item: abs(item[1]), reverse=True)[:10]
    payload = {
        "updated_at": _iso_now(),
        "rank_persistence": {
            "history": history,
            "top_movers": [{"symbol": symbol, "delta": delta} for symbol, delta in top_movers],
        },
        "outcome_analytics": {
            "summary": outcomes_summary,
            "active_samples": active_outcomes[:50],
            "recent_exits": exited[:25],
        },
        "portfolio_simulation": {
            "starting_capital": float(portfolio_starting_capital),
            "cash": round(cash, 2),
            "equity": round(mark_to_market, 2),
            "positions": positions,
            "trades": trades[-100:],
        },
        "data_reliability": {
            "top_low_reliability": [
                {
                    "symbol": str(coin.get("symbol", "")).upper(),
                    "score": coin.get("data_reliability_score"),
                    "source": coin.get("ohlcv_source"),
                }
                for coin in sorted(final_results, key=lambda item: float(item.get("data_reliability_score", 0.0) or 0.0))[:10]
            ],
        },
        "scanner_summary": {
            "all_cmc": len(all_cmc_coins),
            "gain_qualified": len(gain_qualified),
            "processed": len(all_processed),
            "final": len(final_results),
            "entered": len(entered),
            "exited": len(exited),
            "cooldown_blocked": len(blocked_by_cooldown),
        },
    }
    _write_json(path, payload)
    return payload
