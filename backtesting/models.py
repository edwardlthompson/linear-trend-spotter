"""Core data models for deterministic backtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BacktestConfig:
    starting_capital: float = 1000.0
    fee_bps_round_trip: float = 52.0
    trailing_stop_pct: float = 0.0

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
