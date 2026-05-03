"""Persist and diff top-ranked backtest strategy between scans (event summary hook)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_STATE_VERSION = 1


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return float(value)
    if value is None:
        return None
    return str(value)


def fingerprint_from_strategy_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Stable, JSON-serializable fingerprint of the #1 strategy row (params identity)."""
    if not row or str(row.get("indicator", "")).upper() in ("", "B&H"):
        return None
    params_raw = row.get("params") or {}
    if not isinstance(params_raw, dict):
        params_raw = {}
    params_norm = {
        str(k): _json_safe_value(params_raw[k])
        for k in sorted(params_raw.keys(), key=lambda x: str(x))
    }
    tsl = row.get("trailing_stop_loss_pct", row.get("trailing_stop_pct"))
    try:
        tsl_f = float(tsl) if tsl is not None else None
    except (TypeError, ValueError):
        tsl_f = None
    try:
        tp_f = float(row.get("take_profit_pct") or 0.0)
    except (TypeError, ValueError):
        tp_f = 0.0
    try:
        ttp_f = float(row.get("trailing_take_profit_pct") or 0.0)
    except (TypeError, ValueError):
        ttp_f = 0.0
    return {
        "indicator": str(row.get("indicator", "")).strip(),
        "timeframe": str(row.get("timeframe", "")).strip().lower(),
        "params": params_norm,
        "tsl": tsl_f,
        "tp": tp_f,
        "ttp": ttp_f,
    }


def _fingerprints_equal(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(
        b, sort_keys=True, separators=(",", ":")
    )


def _format_tsl(v: float | None) -> str:
    if v is None:
        return "?"
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.1f}"


def _params_delta(prev_p: dict[str, Any], curr_p: dict[str, Any]) -> str | None:
    keys = sorted(set(prev_p.keys()) | set(curr_p.keys()))
    parts: list[str] = []
    for k in keys:
        pv, cv = prev_p.get(k), curr_p.get(k)
        if pv != cv:
            parts.append(f"{k}:{pv}→{cv}")
    if not parts:
        return None
    joined = ",".join(parts[:2])
    if len(parts) > 2:
        joined += "…"
    return joined


def describe_strategy_change(prev: dict[str, Any] | None, curr: dict[str, Any] | None) -> str | None:
    """One compact fragment for a symbol (no symbol prefix). None if no meaningful change."""
    if curr is None:
        if prev is None:
            return None
        return "dropped"
    if prev is None:
        return f"→{curr['indicator']}/{curr['timeframe']}/tsl{_format_tsl(curr.get('tsl'))}"
    if _fingerprints_equal(prev, curr):
        return None
    bits: list[str] = []
    if prev.get("indicator") != curr.get("indicator"):
        bits.append(f"{prev.get('indicator', '?')}→{curr.get('indicator')}")
    if prev.get("timeframe") != curr.get("timeframe"):
        bits.append(f"tf {prev.get('timeframe')}→{curr.get('timeframe')}")
    pd = _params_delta(prev.get("params") or {}, curr.get("params") or {})
    if pd:
        bits.append(pd)
    p_tsl, c_tsl = prev.get("tsl"), curr.get("tsl")
    if p_tsl != c_tsl:
        bits.append(f"tsl {_format_tsl(p_tsl)}→{_format_tsl(c_tsl)}")
    p_tp, c_tp = prev.get("tp"), curr.get("tp")
    if p_tp != c_tp or prev.get("ttp") != curr.get("ttp"):
        bits.append(f"tp {_format_tsl(p_tp)}→{_format_tsl(c_tp)}")
    return "/".join(bits) if bits else "changed"


def build_event_summary_backtest_diff_line(
    *,
    previous_by_symbol: dict[str, Any],
    final_results: list[dict[str, Any]],
    still_qualified_symbols: set[str],
    max_symbols: int = 6,
    max_chars: int = 320,
) -> str | None:
    """Return an HTML-safe plain line (caller may wrap); None if nothing to show."""
    if not previous_by_symbol or not still_qualified_symbols:
        return None

    by_sym: dict[str, dict[str, Any]] = {}
    for coin in final_results:
        sym = str(coin.get("symbol", "")).upper().strip()
        if not sym:
            continue
        by_sym[sym] = coin

    fragments: list[str] = []
    for sym in sorted(still_qualified_symbols):
        if sym not in by_sym:
            continue
        prev_fp = previous_by_symbol.get(sym)
        if isinstance(prev_fp, dict):
            pass
        else:
            prev_fp = None

        strategies = by_sym[sym].get("backtest_top_strategies") or []
        top_row = strategies[0] if strategies else None
        curr_fp = fingerprint_from_strategy_row(top_row if isinstance(top_row, dict) else None)
        desc = describe_strategy_change(
            prev_fp if isinstance(prev_fp, dict) else None,
            curr_fp,
        )
        if desc:
            fragments.append(f"{sym}({desc})")

    if not fragments:
        return None

    shown = fragments[: max(1, max_symbols)]
    extra = len(fragments) - len(shown)
    # Plain text (no HTML); MessageFormatter wraps with <b> and escapes.
    line = "(still active) " + "; ".join(shown)
    if extra > 0:
        line += f" …+{extra}"
    if len(line) > max_chars:
        line = line[: max_chars - 1].rstrip() + "…"
    return line


def load_top_strategy_state(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    ver = raw.get("version")
    block = raw.get("by_symbol") if ver == _STATE_VERSION else raw
    if not isinstance(block, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in block.items():
        sym = str(k).upper().strip()
        if sym and isinstance(v, dict):
            out[sym] = v
    return out


def save_top_strategy_state(path: Path, final_results: list[dict[str, Any]]) -> None:
    by_symbol: dict[str, dict[str, Any]] = {}
    for coin in final_results:
        sym = str(coin.get("symbol", "")).upper().strip()
        if not sym:
            continue
        strategies = coin.get("backtest_top_strategies") or []
        top = strategies[0] if strategies else None
        fp = fingerprint_from_strategy_row(top if isinstance(top, dict) else None)
        if fp is not None:
            by_symbol[sym] = fp

    payload = {"version": _STATE_VERSION, "by_symbol": by_symbol}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
