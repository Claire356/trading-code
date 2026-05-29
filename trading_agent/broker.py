from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import MarketConfig, RiskConfig
from .models import Bar, Position, Trade


@dataclass
class Fill:
    price: float
    quantity: float
    commission_usd: float


class PaperBroker:
    def __init__(self, market_cfg: MarketConfig, risk_cfg: RiskConfig):
        self.market_cfg = market_cfg
        self.risk_cfg = risk_cfg
        self.cash_usd = risk_cfg.initial_capital_usd
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []

    def equity_usd(self, last_price: Optional[float] = None) -> float:
        value = self.cash_usd
        if self.position is not None:
            price = last_price if last_price is not None else self.position.entry_price
            value += self._symbol_to_usd(price * self.position.quantity * self.market_cfg.point_value)
        return value

    def buy(self, bar: Bar, quantity: float, stop_loss: float, take_profit: float, entry_risk: float, reason: str, index: int) -> Fill:
        fill = self._buy_fill(bar.close, quantity)
        cost_usd = self._symbol_to_usd(fill.price * fill.quantity * self.market_cfg.point_value)
        self.cash_usd -= cost_usd + fill.commission_usd
        self.position = Position(
            symbol=self.market_cfg.symbol,
            quantity=fill.quantity,
            entry_price=fill.price,
            entry_time=bar.timestamp,
            entry_index=index,
            initial_stop=stop_loss,
            take_profit=take_profit,
            entry_risk=entry_risk,
            highest_since_entry=bar.high,
            active_stop=stop_loss,
            reason=reason,
        )
        return fill

    def sell(self, bar: Bar, price: float, reason: str) -> Optional[Fill]:
        if self.position is None:
            return None
        fill = self._sell_fill(price, self.position.quantity)
        proceeds_usd = self._symbol_to_usd(fill.price * fill.quantity * self.market_cfg.point_value)
        self.cash_usd += proceeds_usd - fill.commission_usd
        pnl_usd = self._symbol_to_usd((fill.price - self.position.entry_price) * fill.quantity * self.market_cfg.point_value)
        pnl_usd -= self._commission(self.position.entry_price, fill.quantity)
        pnl_usd -= fill.commission_usd
        trade = Trade(
            symbol=self.market_cfg.symbol,
            entry_time=self.position.entry_time,
            exit_time=bar.timestamp,
            quantity=fill.quantity,
            entry_price=self.position.entry_price,
            exit_price=fill.price,
            pnl_usd=pnl_usd,
            return_pct=(fill.price / self.position.entry_price - 1.0) * 100.0,
            entry_reason=self.position.reason,
            exit_reason=reason,
        )
        self.trades.append(trade)
        self.position = None
        return fill

    def _buy_fill(self, close: float, quantity: float) -> Fill:
        price = close * (1.0 + self.risk_cfg.slippage_bps / 10_000.0)
        return Fill(price=price, quantity=quantity, commission_usd=self._commission(price, quantity))

    def _sell_fill(self, price: float, quantity: float) -> Fill:
        fill_price = price * (1.0 - self.risk_cfg.slippage_bps / 10_000.0)
        return Fill(price=fill_price, quantity=quantity, commission_usd=self._commission(fill_price, quantity))

    def _commission(self, price: float, quantity: float) -> float:
        notional_usd = self._symbol_to_usd(price * quantity * self.market_cfg.point_value)
        variable = notional_usd * self.risk_cfg.commission_bps / 10_000.0
        return max(self.risk_cfg.min_commission_usd, variable)

    def _symbol_to_usd(self, amount_symbol_currency: float) -> float:
        if self.market_cfg.usd_to_symbol_fx <= 0:
            raise ValueError("usd_to_symbol_fx must be positive")
        return amount_symbol_currency / self.market_cfg.usd_to_symbol_fx
