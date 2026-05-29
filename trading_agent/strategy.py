from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import AgentConfig
from .indicators import atr, bollinger, dmi, ema, highest, lowest, rsi, sma
from .market_rules import is_regular_session
from .models import Action, Bar, Position, Signal


@dataclass
class FeatureSet:
    ema_fast: List[Optional[float]]
    ema_mid: List[Optional[float]]
    ema_slow: List[Optional[float]]
    di_plus: List[Optional[float]]
    di_minus: List[Optional[float]]
    adx: List[Optional[float]]
    rsi: List[Optional[float]]
    atr: List[Optional[float]]
    donchian_high: List[Optional[float]]
    bb_upper: List[Optional[float]]
    bb_lower: List[Optional[float]]
    volume_ma: List[Optional[float]]
    avg_turnover: List[Optional[float]]
    swing_low: List[Optional[float]]
    benchmark_close: List[Optional[float]]
    benchmark_ema: List[Optional[float]]
    rs_line: List[Optional[float]]
    rs_ma: List[Optional[float]]


class ThreeMarketLongOnlyStrategy:
    def __init__(self, config: AgentConfig):
        self.config = config

    def prepare(self, bars: List[Bar], benchmark_bars: List[Optional[Bar]]) -> FeatureSet:
        s = self.config.strategy
        closes = [bar.close for bar in bars]
        highs = [bar.high for bar in bars]
        lows = [bar.low for bar in bars]
        volumes = [bar.volume for bar in bars]
        turnover = [bar.close * bar.volume for bar in bars]

        benchmark_close = [bar.close if bar is not None else None for bar in benchmark_bars]
        benchmark_close_for_ema = _fill_forward(benchmark_close)
        rs_line = [
            closes[i] / benchmark_close[i] if benchmark_close[i] not in (None, 0) else None
            for i in range(len(bars))
        ]
        rs_for_ma = _fill_forward(rs_line)

        _, bb_upper, bb_lower = bollinger(closes, 20, 2.0)
        di_plus, di_minus, adx_values = dmi(highs, lows, closes, s.adx_len)

        return FeatureSet(
            ema_fast=ema(closes, s.ema_fast_len),
            ema_mid=ema(closes, s.ema_mid_len),
            ema_slow=ema(closes, s.ema_slow_len),
            di_plus=di_plus,
            di_minus=di_minus,
            adx=adx_values,
            rsi=rsi(closes, 14),
            atr=atr(highs, lows, closes, 14),
            donchian_high=highest(highs, s.breakout_len),
            bb_upper=bb_upper,
            bb_lower=bb_lower,
            volume_ma=sma(volumes, s.liquidity_len),
            avg_turnover=sma(turnover, s.liquidity_len),
            swing_low=lowest(lows, self.config.risk.swing_stop_len),
            benchmark_close=benchmark_close,
            benchmark_ema=ema(benchmark_close_for_ema, s.benchmark_ema_len),
            rs_line=rs_line,
            rs_ma=sma(rs_for_ma, s.rs_len),
        )

    def entry_signal(
        self,
        i: int,
        bars: List[Bar],
        features: FeatureSet,
        equity_usd: float,
        day_start_equity_usd: float,
    ) -> Signal:
        bar = bars[i]
        m = self.config.market
        r = self.config.risk
        s = self.config.strategy

        required = [
            features.ema_fast[i],
            features.ema_mid[i],
            features.ema_slow[i],
            features.rsi[i],
            features.atr[i],
            features.volume_ma[i],
            features.avg_turnover[i],
            features.swing_low[i],
        ]
        if any(value is None for value in required):
            return Signal(reason="insufficient_history")

        if not is_regular_session(bar.timestamp, m):
            return Signal(reason="outside_regular_session")

        daily_loss_exceeded = equity_usd <= day_start_equity_usd * (1.0 - r.max_daily_loss_pct / 100.0)
        if daily_loss_exceeded:
            return Signal(reason="daily_loss_lock")

        prev_close = bars[i - 1].close if i > 0 else bar.close
        if m.market.value == "A_SHARES" and bar.close >= prev_close * (1.0 + m.limit_up_avoidance_pct / 100.0):
            return Signal(reason="a_share_limit_up_avoidance")

        atr_value = features.atr[i] or 0.0
        atr_pct = atr_value / bar.close * 100.0 if bar.close > 0 else 0.0
        gap_pct = abs(bar.open / prev_close - 1.0) * 100.0 if prev_close > 0 else 0.0

        trend_ok = self._trend_ok(i, bar, features)
        benchmark_ok = self._benchmark_ok(i, features)
        rs_ok = self._relative_strength_ok(i, features)
        trend_quality_ok = (features.di_plus[i] or 0.0) > (features.di_minus[i] or 0.0) or bar.close > (features.ema_mid[i] or bar.close)
        liquidity_ok = (features.avg_turnover[i] or 0.0) >= s.min_turnover
        price_ok = bar.close >= s.min_price
        atr_ok = s.min_atr_pct <= atr_pct <= s.max_atr_pct
        gap_ok = gap_pct <= s.max_gap_pct
        not_extended = bar.close <= (features.ema_mid[i] or bar.close) + atr_value * s.max_extension_atr

        filters = {
            "trend_ok": trend_ok,
            "benchmark_ok": benchmark_ok,
            "relative_strength_ok": rs_ok,
            "trend_quality_ok": trend_quality_ok,
            "liquidity_ok": liquidity_ok,
            "price_ok": price_ok,
            "atr_ok": atr_ok,
            "gap_ok": gap_ok,
            "not_extended": not_extended,
        }
        if not all(filters.values()):
            failed = [name for name, passed in filters.items() if not passed]
            return Signal(reason="filters_failed:" + ",".join(failed), details={"filters": filters, "atr_pct": atr_pct})

        entry_setups = self._entry_setups(i, bars, features, not_extended)
        if not entry_setups:
            return Signal(reason="no_entry_setup", details={"atr_pct": atr_pct})

        stop_distance = self._entry_stop_distance(i, bar, features)
        quantity = self._position_size(bar.close, stop_distance, equity_usd)
        if quantity < m.lot_size:
            return Signal(reason="position_below_lot_size", details={"raw_stop_distance": stop_distance})

        reason = "+".join(entry_setups)
        return Signal(
            action=Action.BUY,
            reason=reason,
            quantity=quantity,
            stop_loss=bar.close - stop_distance,
            take_profit=bar.close + stop_distance * r.reward_r,
            confidence=min(1.0, 0.5 + len(entry_setups) * 0.15),
            details={"atr_pct": atr_pct, "stop_distance": stop_distance, "filters": filters},
        )

    def update_position_stop(self, i: int, bar: Bar, features: FeatureSet, position: Position) -> None:
        r = self.config.risk
        atr_value = features.atr[i] or 0.0
        position.highest_since_entry = max(position.highest_since_entry, bar.high)
        open_profit_r = (bar.close - position.entry_price) / position.entry_risk if position.entry_risk > 0 else 0.0

        active_stop = max(position.active_stop, position.initial_stop)
        if open_profit_r >= r.breakeven_trigger_r:
            active_stop = max(active_stop, position.entry_price * (1.0 + r.breakeven_buffer_pct / 100.0))
        if open_profit_r >= r.trailing_trigger_r:
            active_stop = max(active_stop, position.highest_since_entry - atr_value * r.trailing_atr_mult)
        position.active_stop = active_stop

    def exit_reason(
        self,
        i: int,
        bars: List[Bar],
        features: FeatureSet,
        position: Position,
        equity_usd: float,
        day_start_equity_usd: float,
    ) -> Optional[str]:
        r = self.config.risk
        bar = bars[i]
        daily_loss_exceeded = equity_usd <= day_start_equity_usd * (1.0 - r.max_daily_loss_pct / 100.0)
        if daily_loss_exceeded:
            return "daily_loss_stop"
        if bar.close < (features.ema_slow[i] or 0.0):
            return "trend_exit"
        if self.config.strategy.use_benchmark_filter and not self._benchmark_ok(i, features):
            return "benchmark_exit"
        if i - position.entry_index >= r.time_stop_bars and bar.close < (features.ema_mid[i] or bar.close):
            return "time_stop"
        return None

    def _trend_ok(self, i: int, bar: Bar, features: FeatureSet) -> bool:
        ema_mid = features.ema_mid[i]
        ema_slow = features.ema_slow[i]
        if ema_mid is None or ema_slow is None or i < 5 or features.ema_slow[i - 5] is None:
            return False
        return bar.close > ema_slow and ema_mid > ema_slow and ema_slow >= features.ema_slow[i - 5]

    def _benchmark_ok(self, i: int, features: FeatureSet) -> bool:
        if not self.config.strategy.use_benchmark_filter:
            return True
        bench = features.benchmark_close[i]
        bench_ema = features.benchmark_ema[i]
        if bench is None or bench_ema is None:
            return True
        if i < 5 or features.benchmark_ema[i - 5] is None:
            return False
        return bench > bench_ema and bench_ema >= features.benchmark_ema[i - 5]

    def _relative_strength_ok(self, i: int, features: FeatureSet) -> bool:
        if not self.config.strategy.use_relative_strength:
            return True
        if features.rs_line[i] is None or features.rs_ma[i] is None:
            return True
        return features.rs_line[i] > features.rs_ma[i]

    def _entry_setups(self, i: int, bars: List[Bar], features: FeatureSet, not_extended: bool) -> List[str]:
        s = self.config.strategy
        bar = bars[i]
        prev = bars[i - 1] if i > 0 else bar
        setups: List[str] = []

        previous_donchian = features.donchian_high[i - 1] if i > 0 else None
        if (
            s.use_breakout
            and previous_donchian is not None
            and bar.close > previous_donchian
            and (features.adx[i] or 0.0) >= s.adx_threshold
            and bar.volume > (features.volume_ma[i] or 0.0) * s.breakout_volume_mult
            and not_extended
        ):
            setups.append("breakout")

        if (
            s.use_pullback
            and bar.low <= (features.ema_mid[i] or bar.low)
            and bar.close > (features.ema_fast[i] or bar.close)
            and bar.close > bar.open
            and s.pullback_rsi_min <= (features.rsi[i] or 0.0) <= s.pullback_rsi_max
        ):
            setups.append("pullback")

        if (
            s.use_reclaim
            and features.bb_lower[i] is not None
            and bar.low < features.bb_lower[i]
            and bar.close > features.bb_lower[i]
            and bar.close > bar.open
            and features.rsi[i] is not None
            and features.rsi[i - 1] is not None
            and features.rsi[i] > features.rsi[i - 1]
            and features.rsi[i] < 60
            and bar.close > prev.low
        ):
            setups.append("bb_reclaim")
        return setups

    def _entry_stop_distance(self, i: int, bar: Bar, features: FeatureSet) -> float:
        r = self.config.risk
        m = self.config.market
        atr_value = features.atr[i] or m.tick_size
        base_stop = atr_value * r.atr_stop_mult
        swing_low = features.swing_low[i] or bar.low
        swing_stop = max(bar.close - swing_low + m.tick_size, m.tick_size)
        return max(base_stop, swing_stop) if r.use_swing_stop else max(base_stop, m.tick_size)

    def _position_size(self, close: float, stop_distance: float, equity_usd: float) -> float:
        m = self.config.market
        r = self.config.risk
        account_risk_symbol = equity_usd * r.risk_per_trade_pct / 100.0 * m.usd_to_symbol_fx
        max_capital_symbol = equity_usd * r.max_position_pct / 100.0 * m.usd_to_symbol_fx
        qty_by_risk = account_risk_symbol / (stop_distance * m.point_value) if stop_distance > 0 else 0.0
        qty_by_capital = max_capital_symbol / (close * m.point_value) if close > 0 else 0.0
        raw_qty = min(qty_by_risk, qty_by_capital)
        return _round_to_lot(raw_qty, m.lot_size)


def _round_to_lot(quantity: float, lot_size: float) -> float:
    if lot_size <= 0:
        return quantity
    return int(quantity / lot_size) * lot_size


def _fill_forward(values: List[Optional[float]]) -> List[float]:
    filled: List[float] = []
    last = 0.0
    for value in values:
        if value is not None:
            last = value
        filled.append(last)
    return filled
