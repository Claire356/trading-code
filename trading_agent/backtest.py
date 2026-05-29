from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional

from .broker import PaperBroker
from .config import AgentConfig
from .data import align_benchmark, load_bars
from .market_rules import is_t1_locked, local_date
from .models import BacktestResult, Bar, PortfolioSnapshot
from .strategy import ThreeMarketLongOnlyStrategy


class Backtester:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.strategy = ThreeMarketLongOnlyStrategy(config)

    def run(self, bars: List[Bar], benchmark_bars: Optional[List[Bar]] = None) -> BacktestResult:
        aligned_benchmark = align_benchmark(bars, benchmark_bars)
        features = self.strategy.prepare(bars, aligned_benchmark)
        broker = PaperBroker(self.config.market, self.config.risk)

        day_start_equity = broker.equity_usd(bars[0].close if bars else None)
        current_day = local_date(bars[0].timestamp, self.config.market.market) if bars else None
        equity_curve: List[PortfolioSnapshot] = []
        peak = self.config.risk.initial_capital_usd
        max_drawdown = 0.0

        for i, bar in enumerate(bars):
            bar_day = local_date(bar.timestamp, self.config.market.market)
            if current_day != bar_day:
                current_day = bar_day
                day_start_equity = broker.equity_usd(bar.close)

            if broker.position is not None:
                position = broker.position
                self.strategy.update_position_stop(i, bar, features, position)
                locked = is_t1_locked(position.entry_time, bar.timestamp, self.config.market)
                if not locked:
                    if bar.low <= position.active_stop:
                        broker.sell(bar, position.active_stop, "stop_loss")
                    elif bar.high >= position.take_profit:
                        broker.sell(bar, position.take_profit, "take_profit")
                    else:
                        reason = self.strategy.exit_reason(i, bars, features, position, broker.equity_usd(bar.close), day_start_equity)
                        if reason is not None:
                            broker.sell(bar, bar.close, reason)

            if broker.position is None:
                signal = self.strategy.entry_signal(i, bars, features, broker.equity_usd(bar.close), day_start_equity)
                if signal.action.value == "BUY" and signal.stop_loss is not None and signal.take_profit is not None:
                    broker.buy(
                        bar=bar,
                        quantity=signal.quantity,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        entry_risk=bar.close - signal.stop_loss,
                        reason=signal.reason,
                        index=i,
                    )

            equity = broker.equity_usd(bar.close)
            peak = max(peak, equity)
            drawdown = equity - peak
            max_drawdown = min(max_drawdown, drawdown)
            equity_curve.append(
                PortfolioSnapshot(
                    timestamp=bar.timestamp,
                    equity_usd=equity,
                    cash_usd=broker.cash_usd,
                    position_value_usd=equity - broker.cash_usd,
                    drawdown_usd=drawdown,
                )
            )

        if bars and broker.position is not None:
            broker.sell(bars[-1], bars[-1].close, "end_of_backtest")
            final_equity = broker.equity_usd(bars[-1].close)
        else:
            final_equity = broker.equity_usd(bars[-1].close if bars else None)

        return BacktestResult(
            initial_equity_usd=self.config.risk.initial_capital_usd,
            final_equity_usd=final_equity,
            max_drawdown_usd=max_drawdown,
            trades=broker.trades,
            equity_curve=equity_curve,
        )


def run_from_config(config: AgentConfig) -> BacktestResult:
    bars = load_bars(config.data.bars_csv)
    benchmark = load_bars(config.data.benchmark_csv) if config.data.benchmark_csv else None
    return Backtester(config).run(bars, benchmark)


def trade_rows(result: BacktestResult):
    for trade in result.trades:
        row = asdict(trade)
        row["entry_time"] = trade.entry_time.isoformat()
        row["exit_time"] = trade.exit_time.isoformat()
        yield row
