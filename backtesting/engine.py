"""Deterministic long-only backtesting engine for Sprint 2.1."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .models import BacktestConfig, BacktestResult, BuyHoldResult, Trade


def _validate_frame(frame: pd.DataFrame) -> None:
    required_columns = {"open", "high", "low", "close", "volume"}
    if frame is None or frame.empty:
        raise ValueError("Input OHLCV frame is empty")
    if set(frame.columns) != required_columns:
        raise ValueError("Input OHLCV frame must include open/high/low/close/volume")


def run_backtest(
    frame: pd.DataFrame,
    buy_signals: pd.Series,
    sell_signals: Optional[pd.Series] = None,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Run deterministic long-only backtest with trailing stop and fees."""
    _validate_frame(frame)

    if config is None:
        config = BacktestConfig()

    aligned_buy = buy_signals.reindex(frame.index).fillna(False).astype(bool)
    aligned_sell = (
        sell_signals.reindex(frame.index).fillna(False).astype(bool)
        if sell_signals is not None
        else pd.Series(False, index=frame.index)
    )

    cash = float(config.starting_capital)
    position_qty = 0.0
    entry_price = 0.0
    entry_fee = 0.0
    highest_price = 0.0
    entry_time = None

    trades: list[Trade] = []

    previous_buy_signal = False

    for timestamp, row in frame.iterrows():
        close_price = float(row["close"])
        high_price = float(row["high"])
        low_price = float(row["low"])

        buy_signal = bool(aligned_buy.loc[timestamp])
        sell_signal = bool(aligned_sell.loc[timestamp])

        new_buy_edge = buy_signal and not previous_buy_signal

        if position_qty > 0:
            if high_price > highest_price:
                highest_price = high_price

            stop_hit = False
            stop_price = None
            if config.trailing_stop_pct > 0:
                stop_price = highest_price * (1 - config.trailing_stop_pct / 100.0)
                stop_hit = low_price <= stop_price

            if stop_hit or sell_signal:
                effective_exit = stop_price if stop_hit and stop_price is not None else close_price
                exit_notional = position_qty * effective_exit
                exit_fee = exit_notional * config.side_fee_rate
                cash = exit_notional - exit_fee
                invested_notional = position_qty * entry_price + entry_fee
                pnl_pct = ((cash - invested_notional) / invested_notional * 100.0) if invested_notional > 0 else 0.0

                trades.append(
                    Trade(
                        entry_time=str(entry_time),
                        entry_price=entry_price,
                        entry_fee=entry_fee,
                        quantity=position_qty,
                        exit_time=str(timestamp),
                        exit_price=effective_exit,
                        exit_fee=exit_fee,
                        pnl_dollars=(position_qty * effective_exit - exit_fee) - invested_notional,
                        pnl_pct=pnl_pct,
                        exit_reason="trailing_stop" if stop_hit else "sell_signal",
                    )
                )

                position_qty = 0.0
                entry_price = 0.0
                entry_fee = 0.0
                highest_price = 0.0
                entry_time = None

        if position_qty == 0 and new_buy_edge:
            entry_notional = cash
            entry_fee = entry_notional * config.side_fee_rate
            net_to_asset = entry_notional - entry_fee
            if net_to_asset > 0 and close_price > 0:
                position_qty = net_to_asset / close_price
                entry_price = close_price
                highest_price = close_price
                entry_time = timestamp
                cash = 0.0

        previous_buy_signal = buy_signal

    if position_qty > 0:
        final_close = float(frame.iloc[-1]["close"])
        exit_notional = position_qty * final_close
        exit_fee = exit_notional * config.side_fee_rate
        cash = exit_notional - exit_fee

        invested_notional = position_qty * entry_price + entry_fee
        pnl_pct = ((cash - invested_notional) / invested_notional * 100.0) if invested_notional > 0 else 0.0
        trades.append(
            Trade(
                entry_time=str(entry_time),
                entry_price=entry_price,
                entry_fee=entry_fee,
                quantity=position_qty,
                exit_time=str(frame.index[-1]),
                exit_price=final_close,
                exit_fee=exit_fee,
                pnl_dollars=(position_qty * final_close - exit_fee) - invested_notional,
                pnl_pct=pnl_pct,
                exit_reason="end_of_data",
            )
        )

    final_equity = float(cash)
    net_pct = ((final_equity - config.starting_capital) / config.starting_capital) * 100.0
    wins = sum(1 for trade in trades if trade.pnl_dollars > 0)
    win_pct = (wins / len(trades) * 100.0) if trades else 0.0

    return BacktestResult(
        final_equity=final_equity,
        net_pct=net_pct,
        total_trades=len(trades),
        win_pct=win_pct,
        trades=trades,
    )


def compute_buy_and_hold(frame: pd.DataFrame, config: Optional[BacktestConfig] = None) -> BuyHoldResult:
    """Compute buy-and-hold baseline from first close to last close with identical fee model."""
    _validate_frame(frame)

    if config is None:
        config = BacktestConfig()

    entry_price = float(frame.iloc[0]["close"])
    exit_price = float(frame.iloc[-1]["close"])

    entry_fee = config.starting_capital * config.side_fee_rate
    quantity = (config.starting_capital - entry_fee) / entry_price

    exit_notional = quantity * exit_price
    exit_fee = exit_notional * config.side_fee_rate
    final_equity = exit_notional - exit_fee

    net_pct = ((final_equity - config.starting_capital) / config.starting_capital) * 100.0

    return BuyHoldResult(
        final_equity=final_equity,
        net_pct=net_pct,
        entry_price=entry_price,
        exit_price=exit_price,
    )
