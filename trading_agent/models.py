from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class Market(str, Enum):
    US = "US"
    A_SHARES = "A_SHARES"
    HK = "HK"


class Action(str, Enum):
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    action: Action = Action.HOLD
    reason: str = ""
    quantity: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    entry_index: int
    initial_stop: float
    take_profit: float
    entry_risk: float
    highest_since_entry: float
    active_stop: float
    reason: str


@dataclass
class Trade:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    quantity: float
    entry_price: float
    exit_price: float
    pnl_usd: float
    return_pct: float
    entry_reason: str
    exit_reason: str


@dataclass
class RuntimeState:
    cash_usd: float
    day_start_equity_usd: float
    current_day: Optional[str] = None
    last_bar_timestamp: Optional[str] = None
    position: Optional[Position] = None
    trades: List[Trade] = field(default_factory=list)


@dataclass
class AgentStepResult:
    timestamp: datetime
    symbol: str
    action: Action
    reason: str
    equity_usd: float
    cash_usd: float
    position: Optional[Position] = None
    order: Optional[dict] = None
    fill: Optional[dict] = None
    details: dict = field(default_factory=dict)


@dataclass
class PortfolioSnapshot:
    timestamp: datetime
    equity_usd: float
    cash_usd: float
    position_value_usd: float
    drawdown_usd: float


@dataclass
class BacktestResult:
    initial_equity_usd: float
    final_equity_usd: float
    max_drawdown_usd: float
    trades: List[Trade]
    equity_curve: List[PortfolioSnapshot]

    @property
    def total_return_pct(self) -> float:
        if self.initial_equity_usd == 0:
            return 0.0
        return (self.final_equity_usd / self.initial_equity_usd - 1.0) * 100.0

    @property
    def win_rate_pct(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for trade in self.trades if trade.pnl_usd > 0)
        return wins / len(self.trades) * 100.0

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(trade.pnl_usd for trade in self.trades if trade.pnl_usd > 0)
        gross_loss = -sum(trade.pnl_usd for trade in self.trades if trade.pnl_usd < 0)
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss
