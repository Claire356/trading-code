from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .config import AgentConfig
from .models import Position, RuntimeState, Trade


class JsonStateStore:
    def __init__(self, path: str, config: AgentConfig):
        self.path = Path(path)
        self.config = config

    def load(self) -> RuntimeState:
        if not self.path.exists():
            return RuntimeState(
                cash_usd=self.config.risk.initial_capital_usd,
                day_start_equity_usd=self.config.risk.initial_capital_usd,
            )

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        position = _position_from_dict(raw.get("position"))
        trades = [_trade_from_dict(item) for item in raw.get("trades", [])]
        return RuntimeState(
            cash_usd=float(raw.get("cash_usd", self.config.risk.initial_capital_usd)),
            day_start_equity_usd=float(raw.get("day_start_equity_usd", self.config.risk.initial_capital_usd)),
            current_day=raw.get("current_day"),
            last_bar_timestamp=raw.get("last_bar_timestamp"),
            position=position,
            trades=trades,
        )

    def save(self, state: RuntimeState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cash_usd": state.cash_usd,
            "day_start_equity_usd": state.day_start_equity_usd,
            "current_day": state.current_day,
            "last_bar_timestamp": state.last_bar_timestamp,
            "position": _position_to_dict(state.position),
            "trades": [_trade_to_dict(trade) for trade in state.trades],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()


def state_equity_usd(state: RuntimeState, config: AgentConfig, last_price: Optional[float]) -> float:
    equity = state.cash_usd
    if state.position is not None and last_price is not None:
        equity += symbol_to_usd(last_price * state.position.quantity * config.market.point_value, config)
    return equity


def symbol_to_usd(amount_symbol_currency: float, config: AgentConfig) -> float:
    if config.market.usd_to_symbol_fx <= 0:
        raise ValueError("usd_to_symbol_fx must be positive")
    return amount_symbol_currency / config.market.usd_to_symbol_fx


def usd_to_symbol(amount_usd: float, config: AgentConfig) -> float:
    return amount_usd * config.market.usd_to_symbol_fx


def commission_usd(price: float, quantity: float, config: AgentConfig) -> float:
    notional_usd = symbol_to_usd(price * quantity * config.market.point_value, config)
    variable = notional_usd * config.risk.commission_bps / 10_000.0
    return max(config.risk.min_commission_usd, variable)


def _position_to_dict(position: Optional[Position]) -> Optional[Dict[str, Any]]:
    if position is None:
        return None
    return {
        "symbol": position.symbol,
        "quantity": position.quantity,
        "entry_price": position.entry_price,
        "entry_time": position.entry_time.isoformat(),
        "entry_index": position.entry_index,
        "initial_stop": position.initial_stop,
        "take_profit": position.take_profit,
        "entry_risk": position.entry_risk,
        "highest_since_entry": position.highest_since_entry,
        "active_stop": position.active_stop,
        "reason": position.reason,
    }


def _position_from_dict(raw: Optional[Dict[str, Any]]) -> Optional[Position]:
    if raw is None:
        return None
    from datetime import datetime

    return Position(
        symbol=raw["symbol"],
        quantity=float(raw["quantity"]),
        entry_price=float(raw["entry_price"]),
        entry_time=datetime.fromisoformat(raw["entry_time"]),
        entry_index=int(raw["entry_index"]),
        initial_stop=float(raw["initial_stop"]),
        take_profit=float(raw["take_profit"]),
        entry_risk=float(raw["entry_risk"]),
        highest_since_entry=float(raw["highest_since_entry"]),
        active_stop=float(raw["active_stop"]),
        reason=raw["reason"],
    )


def _trade_to_dict(trade: Trade) -> Dict[str, Any]:
    return {
        "symbol": trade.symbol,
        "entry_time": trade.entry_time.isoformat(),
        "exit_time": trade.exit_time.isoformat(),
        "quantity": trade.quantity,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "pnl_usd": trade.pnl_usd,
        "return_pct": trade.return_pct,
        "entry_reason": trade.entry_reason,
        "exit_reason": trade.exit_reason,
    }


def _trade_from_dict(raw: Dict[str, Any]) -> Trade:
    from datetime import datetime

    return Trade(
        symbol=raw["symbol"],
        entry_time=datetime.fromisoformat(raw["entry_time"]),
        exit_time=datetime.fromisoformat(raw["exit_time"]),
        quantity=float(raw["quantity"]),
        entry_price=float(raw["entry_price"]),
        exit_price=float(raw["exit_price"]),
        pnl_usd=float(raw["pnl_usd"]),
        return_pct=float(raw["return_pct"]),
        entry_reason=raw["entry_reason"],
        exit_reason=raw["exit_reason"],
    )
