"""Core data models for deterministic backtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BacktestConfig:
    starting_capital: float
    fee_bps_round_trip: float
    trailing_stop_loss_pct: float
    take_profit_pct: float
    trailing_take_profit_pct: float

    def __init__(
        self,
        starting_capital: float = 1000.0,
        fee_bps_round_trip: float = 52.0,
        trailing_stop_loss_pct: float = 1.0,
        take_profit_pct: float = 0.0,
        trailing_take_profit_pct: float = 0.0,
        trailing_stop_pct: float | None = None,
    ) -> None:
        self.starting_capital = float(starting_capital)
        self.fee_bps_round_trip = float(fee_bps_round_trip)
        resolved_tsl = float(
            trailing_stop_loss_pct if trailing_stop_pct is None else trailing_stop_pct
        )
        if resolved_tsl < 1.0:
            raise ValueError("trailing_stop_loss_pct must be >= 1.0")
        self.trailing_stop_loss_pct = resolved_tsl
        self.take_profit_pct = float(take_profit_pct)
        self.trailing_take_profit_pct = float(trailing_take_profit_pct)

    @property
    def trailing_stop_pct(self) -> float:
        return float(self.trailing_stop_loss_pct)

    @trailing_stop_pct.setter
    def trailing_stop_pct(self, value: float) -> None:
        resolved = float(value)
        if resolved < 1.0:
            raise ValueError("trailing_stop_loss_pct must be >= 1.0")
        self.trailing_stop_loss_pct = resolved

    @property
    def side_fee_rate(self) -> float:
        return (self.fee_bps_round_trip / 10000.0) / 2.0


@dataclass
class Trade:
    entry_time: str
    entry_price: float
    entry_fee: float
    quantity: float
    exit_time: str
    exit_price: float
    exit_fee: float
    pnl_dollars: float
    pnl_pct: float
    exit_reason: str


@dataclass
class BacktestResult:
    final_equity: float
    net_pct: float
    total_trades: int
    win_pct: float
    trades: list[Trade] = field(default_factory=list)


@dataclass
class BuyHoldResult:
    final_equity: float
    net_pct: float
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
