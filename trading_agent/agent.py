from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from .backtest import Backtester
from .config import AgentConfig, load_config
from .data import align_benchmark, load_bars
from .models import BacktestResult, Signal
from .strategy import ThreeMarketLongOnlyStrategy


class TradingAgent:
    """High-level agent facade for signal generation and backtesting."""

    def __init__(self, config: AgentConfig):
        self.config = config

    @classmethod
    def from_config_file(cls, path: str) -> "TradingAgent":
        return cls(load_config(path))

    def latest_signal(
        self,
        equity_usd: Optional[float] = None,
        day_start_equity_usd: Optional[float] = None,
    ) -> Signal:
        bars = load_bars(self.config.data.bars_csv)
        benchmark = load_bars(self.config.data.benchmark_csv) if self.config.data.benchmark_csv else None
        aligned_benchmark = align_benchmark(bars, benchmark)
        strategy = ThreeMarketLongOnlyStrategy(self.config)
        features = strategy.prepare(bars, aligned_benchmark)
        account_equity = equity_usd if equity_usd is not None else self.config.risk.initial_capital_usd
        day_equity = day_start_equity_usd if day_start_equity_usd is not None else account_equity
        return strategy.entry_signal(len(bars) - 1, bars, features, account_equity, day_equity)

    def backtest(self) -> BacktestResult:
        bars = load_bars(self.config.data.bars_csv)
        benchmark = load_bars(self.config.data.benchmark_csv) if self.config.data.benchmark_csv else None
        return Backtester(self.config).run(bars, benchmark)

    def latest_signal_payload(self) -> dict:
        signal = self.latest_signal()
        payload = asdict(signal)
        payload["action"] = signal.action.value
        payload["symbol"] = self.config.market.symbol
        return payload
