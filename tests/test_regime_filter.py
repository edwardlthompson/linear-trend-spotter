"""BTC regime gate must read nested top-coin provider rows."""

from __future__ import annotations

from scanner.regime_filter import evaluate_regime_gate
from scanner.uniformity_stages import apply_uniformity_pass_and_regime


class _Settings:
    uniformity_min_score = 50.0
    regime_filter_enabled = True
    regime_filter_btc_min_30d_gain = 0.0
    regime_filter_btc_max_abs_7d_gain = 25.0


class _Logger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None


def test_evaluate_regime_gate_reads_nested_info_symbol() -> None:
    nested = [
        {
            "data": {"symbol": "btc"},
            "gains": {"7d": -40.0, "30d": -12.0},
            "info": {"symbol": "BTC", "name": "Bitcoin"},
        }
    ]
    ok, reason, ctx = evaluate_regime_gate(
        nested,
        btc_min_30d_gain=0.0,
        btc_max_abs_7d_gain=25.0,
    )
    assert ok is False
    assert "btc_30d_below_min" in reason
    assert ctx["btc_30d"] == -12.0


def test_apply_uniformity_pass_and_regime_blocks_on_nested_btc() -> None:
    processed = [
        {
            "symbol": "AAA",
            "uniformity_score": 90.0,
            "total_gain": 20.0,
        }
    ]
    all_cmc = [
        {
            "gains": {"7d": 5.0, "30d": -8.0},
            "info": {"symbol": "BTC"},
        }
    ]
    passed, symbols, meta = apply_uniformity_pass_and_regime(
        processed,
        all_cmc,
        settings=_Settings(),
        app_logger=_Logger(),
    )
    assert passed == []
    assert symbols == set()
    assert meta is not None
    assert meta["passed"] is False
    assert meta["blocked"] is True
    assert meta["reason"].startswith("btc_30d_below_min")
