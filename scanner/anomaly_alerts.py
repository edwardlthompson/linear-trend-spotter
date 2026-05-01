"""Anomaly alert message helpers (extracted from main.py, Milestone I2)."""

from __future__ import annotations


def build_anomaly_messages(
    *,
    total_gain_qualified: int,
    missing_cg_count: int,
    no_ticker_count: int,
    cg_mapped_count: int,
    processed_ohlcv_count: int,
    max_missing_cg_ratio: float,
    max_no_ticker_ratio: float,
    min_ohlcv_success_ratio: float,
) -> list[str]:
    messages: list[str] = []

    if total_gain_qualified > 0:
        missing_cg_ratio = missing_cg_count / total_gain_qualified
        if missing_cg_ratio > max_missing_cg_ratio:
            messages.append(
                "High CoinGecko mapping miss ratio "
                f"({missing_cg_count}/{total_gain_qualified}, {missing_cg_ratio:.0%})"
            )

    if cg_mapped_count > 0:
        no_ticker_ratio = no_ticker_count / cg_mapped_count
        if no_ticker_ratio > max_no_ticker_ratio:
            messages.append(
                "High no-ticker ratio "
                f"({no_ticker_count}/{cg_mapped_count}, {no_ticker_ratio:.0%})"
            )

        ohlcv_success_ratio = processed_ohlcv_count / cg_mapped_count
        if ohlcv_success_ratio < min_ohlcv_success_ratio:
            messages.append(
                "Low OHLCV success ratio "
                f"({processed_ohlcv_count}/{cg_mapped_count}, {ohlcv_success_ratio:.0%})"
            )

    return messages
