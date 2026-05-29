from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from .config import AgentConfig, load_config
from .data import align_benchmark, load_bars
from .market_rules import is_t1_locked, local_date
from .models import Action, AgentStepResult, Bar, Position, RuntimeState, Trade
from .state import JsonStateStore, commission_usd, state_equity_usd, symbol_to_usd
from .strategy import ThreeMarketLongOnlyStrategy


class PaperAgentRuntime:
    """Single-symbol, run-once paper runtime with persistent JSON state."""

    def __init__(self, config: AgentConfig, state_store: JsonStateStore):
        self.config = config
        self.state_store = state_store
        self.strategy = ThreeMarketLongOnlyStrategy(config)

    @classmethod
    def from_files(cls, config_path: str, state_path: str) -> "PaperAgentRuntime":
        config = load_config(config_path)
        return cls(config, JsonStateStore(state_path, config))

    def run_once(self, allow_reprocess: bool = False) -> AgentStepResult:
        bars = load_bars(self.config.data.bars_csv)
        if not bars:
            raise ValueError("No bars available")
        benchmark = load_bars(self.config.data.benchmark_csv) if self.config.data.benchmark_csv else None
        aligned_benchmark = align_benchmark(bars, benchmark)
        features = self.strategy.prepare(bars, aligned_benchmark)
        i = len(bars) - 1
        bar = bars[i]
        bar_key = bar.timestamp.isoformat()

        state = self.state_store.load()
        if state.last_bar_timestamp == bar_key and not allow_reprocess:
            equity = state_equity_usd(state, self.config, bar.close)
            return self._result(bar, state, Action.HOLD, "bar_already_processed", equity)

        self._roll_day_if_needed(state, bar)
        equity_before = state_equity_usd(state, self.config, bar.close)

        result: AgentStepResult
        if state.position is not None:
            result = self._manage_position(state, i, bars, features, equity_before)
        else:
            result = self._maybe_enter(state, i, bars, features, equity_before)

        state.last_bar_timestamp = bar_key
        self.state_store.save(state)
        return result

    def _manage_position(self, state: RuntimeState, i: int, bars, features, equity_before: float) -> AgentStepResult:
        bar = bars[i]
        assert state.position is not None
        position = state.position
        self.strategy.update_position_stop(i, bar, features, position)

        locked = is_t1_locked(position.entry_time, bar.timestamp, self.config.market)
        if locked:
            equity = state_equity_usd(state, self.config, bar.close)
            return self._result(bar, state, Action.HOLD, "a_share_t1_locked", equity, details={"active_stop": position.active_stop})

        exit_price: Optional[float] = None
        reason: Optional[str] = None
        if bar.low <= position.active_stop:
            exit_price = position.active_stop
            reason = "stop_loss"
        elif bar.high >= position.take_profit:
            exit_price = position.take_profit
            reason = "take_profit"
        else:
            reason = self.strategy.exit_reason(i, bars, features, position, equity_before, state.day_start_equity_usd)
            if reason is not None:
                exit_price = bar.close

        if exit_price is None or reason is None:
            equity = state_equity_usd(state, self.config, bar.close)
            return self._result(bar, state, Action.HOLD, "position_held", equity, details={"active_stop": position.active_stop})

        fill_price = exit_price * (1.0 - self.config.risk.slippage_bps / 10_000.0)
        commission = commission_usd(fill_price, position.quantity, self.config)
        proceeds_usd = symbol_to_usd(fill_price * position.quantity * self.config.market.point_value, self.config)
        state.cash_usd += proceeds_usd - commission

        entry_commission = commission_usd(position.entry_price, position.quantity, self.config)
        pnl_usd = symbol_to_usd((fill_price - position.entry_price) * position.quantity * self.config.market.point_value, self.config)
        pnl_usd -= entry_commission + commission
        trade = Trade(
            symbol=self.config.market.symbol,
            entry_time=position.entry_time,
            exit_time=bar.timestamp,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=fill_price,
            pnl_usd=pnl_usd,
            return_pct=(fill_price / position.entry_price - 1.0) * 100.0,
            entry_reason=position.reason,
            exit_reason=reason,
        )
        state.trades.append(trade)
        state.position = None
        equity = state_equity_usd(state, self.config, bar.close)
        return self._result(
            bar,
            state,
            Action.SELL,
            reason,
            equity,
            order={"side": "SELL", "quantity": position.quantity, "price": exit_price},
            fill={"price": fill_price, "commission_usd": commission, "pnl_usd": pnl_usd},
        )

    def _maybe_enter(self, state: RuntimeState, i: int, bars, features, equity_before: float) -> AgentStepResult:
        bar = bars[i]
        signal = self.strategy.entry_signal(i, bars, features, equity_before, state.day_start_equity_usd)
        if signal.action != Action.BUY or signal.stop_loss is None or signal.take_profit is None:
            equity = state_equity_usd(state, self.config, bar.close)
            return self._result(bar, state, Action.HOLD, signal.reason, equity, details=signal.details)

        fill_price = bar.close * (1.0 + self.config.risk.slippage_bps / 10_000.0)
        commission = commission_usd(fill_price, signal.quantity, self.config)
        cost_usd = symbol_to_usd(fill_price * signal.quantity * self.config.market.point_value, self.config)
        if state.cash_usd < cost_usd + commission:
            equity = state_equity_usd(state, self.config, bar.close)
            return self._result(
                bar,
                state,
                Action.HOLD,
                "insufficient_cash",
                equity,
                details={"needed_usd": cost_usd + commission, "cash_usd": state.cash_usd},
            )

        state.cash_usd -= cost_usd + commission
        entry_risk = max(fill_price - signal.stop_loss, self.config.market.tick_size)
        state.position = Position(
            symbol=self.config.market.symbol,
            quantity=signal.quantity,
            entry_price=fill_price,
            entry_time=bar.timestamp,
            entry_index=i,
            initial_stop=signal.stop_loss,
            take_profit=signal.take_profit,
            entry_risk=entry_risk,
            highest_since_entry=bar.high,
            active_stop=signal.stop_loss,
            reason=signal.reason,
        )
        equity = state_equity_usd(state, self.config, bar.close)
        return self._result(
            bar,
            state,
            Action.BUY,
            signal.reason,
            equity,
            order={"side": "BUY", "quantity": signal.quantity, "price": bar.close, "stop_loss": signal.stop_loss, "take_profit": signal.take_profit},
            fill={"price": fill_price, "commission_usd": commission},
            details=signal.details,
        )

    def _roll_day_if_needed(self, state: RuntimeState, bar: Bar) -> None:
        day_key = local_date(bar.timestamp, self.config.market.market).isoformat()
        if state.current_day != day_key:
            state.current_day = day_key
            state.day_start_equity_usd = state_equity_usd(state, self.config, bar.close)

    def _result(
        self,
        bar: Bar,
        state: RuntimeState,
        action: Action,
        reason: str,
        equity_usd: float,
        order: Optional[dict] = None,
        fill: Optional[dict] = None,
        details: Optional[dict] = None,
    ) -> AgentStepResult:
        return AgentStepResult(
            timestamp=bar.timestamp,
            symbol=self.config.market.symbol,
            action=action,
            reason=reason,
            equity_usd=equity_usd,
            cash_usd=state.cash_usd,
            position=state.position,
            order=order,
            fill=fill,
            details=details or {},
        )


def step_result_to_dict(result: AgentStepResult) -> dict:
    payload = asdict(result)
    payload["timestamp"] = result.timestamp.isoformat()
    payload["action"] = result.action.value
    if result.position is not None:
        payload["position"]["entry_time"] = result.position.entry_time.isoformat()
    return payload
