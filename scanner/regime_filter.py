"""Optional market regime gate (Milestone O2)."""

from __future__ import annotations

from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def evaluate_regime_gate(
    all_cmc_coins: list[dict[str, Any]],
    *,
    btc_min_30d_gain: float,
    btc_max_abs_7d_gain: float,
) -> tuple[bool, str, dict[str, float]]:
    """Return (allowed, reason, context) using BTC momentum/volatility as regime proxy."""
    btc = None
    for item in all_cmc_coins or []:
        if str(item.get("symbol", "")).upper() == "BTC":
            btc = item
            break

    if not isinstance(btc, dict):
        return True, "btc_missing_allow", {}

    gains = btc.get("gains") if isinstance(btc.get("gains"), dict) else {}
    g7 = _as_float(gains.get("7d", btc.get("gain_7d", 0.0)))
    g30 = _as_float(gains.get("30d", btc.get("gain_30d", 0.0)))
    context = {"btc_7d": g7, "btc_30d": g30}

    if g30 < float(btc_min_30d_gain):
        return False, f"btc_30d_below_min ({g30:.2f} < {float(btc_min_30d_gain):.2f})", context

    if abs(g7) > float(btc_max_abs_7d_gain):
        return False, f"btc_7d_abs_above_max ({abs(g7):.2f} > {float(btc_max_abs_7d_gain):.2f})", context

    return True, "ok", context
