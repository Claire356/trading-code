from __future__ import annotations

import unittest
import csv
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from trading_agent.backtest import Backtester
from trading_agent.config import AgentConfig, DataConfig, MarketConfig, RiskConfig, StrategyConfig
from trading_agent.indicators import ema, rsi
from trading_agent.market_rules import is_regular_session
from trading_agent.models import Bar, Market
from trading_agent.runtime import PaperAgentRuntime
from trading_agent.state import JsonStateStore


class IndicatorTests(unittest.TestCase):
    def test_ema_and_rsi_produce_values(self):
        closes = [float(i) for i in range(1, 40)]
        self.assertIsNotNone(ema(closes, 10)[-1])
        self.assertGreater(rsi(closes, 14)[-1], 90)


class MarketRuleTests(unittest.TestCase):
    def test_us_regular_session(self):
        cfg = MarketConfig(symbol="AAPL", market=Market.US)
        self.assertTrue(is_regular_session(datetime.fromisoformat("2025-01-02T10:00:00-05:00"), cfg))
        self.assertFalse(is_regular_session(datetime.fromisoformat("2025-01-02T08:00:00-05:00"), cfg))

    def test_a_share_lunch_break(self):
        cfg = MarketConfig(symbol="600000", market=Market.A_SHARES, currency="CNY", usd_to_symbol_fx=7.2, lot_size=100)
        self.assertFalse(is_regular_session(datetime.fromisoformat("2025-01-02T12:00:00+08:00"), cfg))


class BacktestTests(unittest.TestCase):
    def test_backtest_runs_and_can_trade(self):
        bars = _sample_bars(120)
        config = AgentConfig(
            market=MarketConfig(symbol="TEST", market=Market.US),
            data=DataConfig(bars_csv="unused.csv"),
            strategy=StrategyConfig(
                use_benchmark_filter=False,
                use_relative_strength=False,
                ema_fast_len=5,
                ema_mid_len=10,
                ema_slow_len=30,
                breakout_len=10,
                adx_threshold=0,
                min_turnover=0,
                min_price=0,
                min_atr_pct=0,
                max_atr_pct=100,
                max_extension_atr=100,
                breakout_volume_mult=0.5,
            ),
            risk=RiskConfig(initial_capital_usd=100000, commission_bps=0, min_commission_usd=0, slippage_bps=0),
        )
        result = Backtester(config).run(bars, bars)
        self.assertGreaterEqual(len(result.trades), 1)
        self.assertGreater(result.final_equity_usd, 0)


class RuntimeTests(unittest.TestCase):
    def test_run_once_persists_last_processed_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "bars.csv"
            state_path = Path(tmp) / "state.json"
            _write_bars(data_path, _sample_bars(80))
            config = AgentConfig(
                market=MarketConfig(symbol="TEST", market=Market.US),
                data=DataConfig(bars_csv=str(data_path)),
                strategy=StrategyConfig(
                    use_benchmark_filter=False,
                    use_relative_strength=False,
                    ema_fast_len=5,
                    ema_mid_len=10,
                    ema_slow_len=30,
                    breakout_len=10,
                    adx_threshold=0,
                    min_turnover=0,
                    min_price=0,
                    min_atr_pct=0,
                    max_atr_pct=100,
                    max_extension_atr=100,
                    breakout_volume_mult=0.5,
                ),
                risk=RiskConfig(initial_capital_usd=100000, commission_bps=0, min_commission_usd=0, slippage_bps=0),
            )
            runtime = PaperAgentRuntime(config, JsonStateStore(str(state_path), config))
            first = runtime.run_once()
            second = runtime.run_once()
            self.assertTrue(state_path.exists())
            self.assertEqual(second.reason, "bar_already_processed")
            self.assertEqual(first.timestamp, second.timestamp)


def _sample_bars(count: int):
    bars = []
    price = 100.0
    timestamp = datetime.fromisoformat("2024-01-02T00:00:00")
    while len(bars) < count:
        open_price = price
        close = price + 1.0
        bars.append(Bar(timestamp=timestamp, open=open_price, high=close + 0.1, low=open_price - 0.1, close=close, volume=1_000_000))
        price = close
        timestamp += timedelta(days=1)
    return bars


def _write_bars(path: Path, bars):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        for bar in bars:
            writer.writerow(
                {
                    "timestamp": bar.timestamp.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
            )


if __name__ == "__main__":
    unittest.main()
