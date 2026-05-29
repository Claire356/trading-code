from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .models import Market


@dataclass
class MarketConfig:
    symbol: str
    market: Market
    currency: str = "USD"
    usd_to_symbol_fx: float = 1.0
    lot_size: float = 1.0
    tick_size: float = 0.01
    point_value: float = 1.0
    use_session_filter: bool = True
    enforce_t1: bool = True
    limit_up_avoidance_pct: float = 9.7


@dataclass
class DataConfig:
    bars_csv: str
    benchmark_csv: Optional[str] = None


@dataclass
class StrategyConfig:
    use_benchmark_filter: bool = True
    use_relative_strength: bool = True
    benchmark_ema_len: int = 100
    rs_len: int = 50
    ema_fast_len: int = 20
    ema_mid_len: int = 50
    ema_slow_len: int = 200
    adx_len: int = 14
    adx_threshold: float = 18.0
    breakout_len: int = 55
    pullback_rsi_min: float = 42.0
    pullback_rsi_max: float = 68.0
    use_breakout: bool = True
    use_pullback: bool = True
    use_reclaim: bool = True
    liquidity_len: int = 20
    min_turnover: float = 5_000_000.0
    min_price: float = 5.0
    min_atr_pct: float = 0.4
    max_atr_pct: float = 8.0
    max_gap_pct: float = 6.0
    max_extension_atr: float = 2.5
    breakout_volume_mult: float = 1.15


@dataclass
class RiskConfig:
    initial_capital_usd: float = 100_000.0
    risk_per_trade_pct: float = 0.75
    max_position_pct: float = 25.0
    max_daily_loss_pct: float = 2.5
    atr_stop_mult: float = 2.5
    use_swing_stop: bool = True
    swing_stop_len: int = 10
    reward_r: float = 3.0
    breakeven_trigger_r: float = 1.2
    breakeven_buffer_pct: float = 0.05
    trailing_trigger_r: float = 1.8
    trailing_atr_mult: float = 2.2
    time_stop_bars: int = 60
    commission_bps: float = 1.0
    min_commission_usd: float = 1.0
    slippage_bps: float = 2.0


@dataclass
class AgentConfig:
    market: MarketConfig
    data: DataConfig
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


def _dataclass_from_dict(cls: Any, values: Dict[str, Any]) -> Any:
    field_names = set(cls.__dataclass_fields__.keys())
    filtered = {key: value for key, value in values.items() if key in field_names}
    return cls(**filtered)


def load_config(path: str) -> AgentConfig:
    config_path = Path(path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    market_values = dict(raw["market"])
    market_values["market"] = Market(market_values["market"])
    market = _dataclass_from_dict(MarketConfig, market_values)
    data = _dataclass_from_dict(DataConfig, raw["data"])
    strategy = _dataclass_from_dict(StrategyConfig, raw.get("strategy", {}))
    risk = _dataclass_from_dict(RiskConfig, raw.get("risk", {}))
    return AgentConfig(market=market, data=data, strategy=strategy, risk=risk)


def sample_config(market: Market) -> Dict[str, Any]:
    if market == Market.A_SHARES:
        market_cfg = {
            "symbol": "600000",
            "market": Market.A_SHARES.value,
            "currency": "CNY",
            "usd_to_symbol_fx": 7.2,
            "lot_size": 100,
            "tick_size": 0.01,
            "use_session_filter": True,
            "enforce_t1": True,
            "limit_up_avoidance_pct": 9.7,
        }
        strategy_cfg = {"min_turnover": 30_000_000, "min_price": 3.0}
    elif market == Market.HK:
        market_cfg = {
            "symbol": "00700",
            "market": Market.HK.value,
            "currency": "HKD",
            "usd_to_symbol_fx": 7.8,
            "lot_size": 100,
            "tick_size": 0.01,
            "use_session_filter": True,
            "enforce_t1": False,
        }
        strategy_cfg = {"min_turnover": 10_000_000, "min_price": 2.0}
    else:
        market_cfg = {
            "symbol": "AAPL",
            "market": Market.US.value,
            "currency": "USD",
            "usd_to_symbol_fx": 1.0,
            "lot_size": 1,
            "tick_size": 0.01,
            "use_session_filter": True,
            "enforce_t1": False,
        }
        strategy_cfg = {"min_turnover": 5_000_000, "min_price": 5.0}

    strategy_cfg.update(
        {
            "benchmark_ema_len": 30,
            "rs_len": 20,
            "ema_fast_len": 8,
            "ema_mid_len": 21,
            "ema_slow_len": 50,
            "breakout_len": 20,
        }
    )

    return {
        "market": market_cfg,
        "data": {"bars_csv": "data/sample_us.csv", "benchmark_csv": "data/sample_us.csv"},
        "strategy": strategy_cfg,
        "risk": {
            "initial_capital_usd": 100000,
            "risk_per_trade_pct": 0.75,
            "max_position_pct": 25,
            "commission_bps": 1.0,
            "slippage_bps": 2.0,
        },
    }
