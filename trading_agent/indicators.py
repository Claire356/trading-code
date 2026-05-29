from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Number = Optional[float]


def sma(values: Sequence[float], period: int) -> List[Number]:
    out: List[Number] = [None] * len(values)
    if period <= 0:
        return out
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= period:
            total -= values[i - period]
        if i >= period - 1:
            out[i] = total / period
    return out


def ema(values: Sequence[float], period: int) -> List[Number]:
    out: List[Number] = [None] * len(values)
    if period <= 0 or not values:
        return out
    alpha = 2.0 / (period + 1.0)
    seed_sum = 0.0
    ema_value = None
    for i, value in enumerate(values):
        if i < period:
            seed_sum += value
            if i == period - 1:
                ema_value = seed_sum / period
                out[i] = ema_value
            continue
        assert ema_value is not None
        ema_value = value * alpha + ema_value * (1.0 - alpha)
        out[i] = ema_value
    return out


def highest(values: Sequence[float], period: int) -> List[Number]:
    out: List[Number] = [None] * len(values)
    for i in range(len(values)):
        if i >= period - 1:
            out[i] = max(values[i - period + 1 : i + 1])
    return out


def lowest(values: Sequence[float], period: int) -> List[Number]:
    out: List[Number] = [None] * len(values)
    for i in range(len(values)):
        if i >= period - 1:
            out[i] = min(values[i - period + 1 : i + 1])
    return out


def rolling_std(values: Sequence[float], period: int) -> List[Number]:
    out: List[Number] = [None] * len(values)
    for i in range(len(values)):
        if i >= period - 1:
            window = values[i - period + 1 : i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            out[i] = math.sqrt(variance)
    return out


def rsi(values: Sequence[float], period: int = 14) -> List[Number]:
    out: List[Number] = [None] * len(values)
    if len(values) <= period:
        return out

    gains = [0.0] * len(values)
    losses = [0.0] * len(values)
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains[i] = max(change, 0.0)
        losses[i] = max(-change, 0.0)

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    out[period] = _rsi_from_avgs(avg_gain, avg_loss)

    for i in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _rsi_from_avgs(avg_gain, avg_loss)
    return out


def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def true_range(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> List[float]:
    out: List[float] = [0.0] * len(closes)
    for i in range(len(closes)):
        if i == 0:
            out[i] = highs[i] - lows[i]
        else:
            out[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    return out


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> List[Number]:
    tr = true_range(highs, lows, closes)
    out: List[Number] = [None] * len(closes)
    if len(tr) < period:
        return out
    atr_value = sum(tr[:period]) / period
    out[period - 1] = atr_value
    for i in range(period, len(tr)):
        atr_value = (atr_value * (period - 1) + tr[i]) / period
        out[i] = atr_value
    return out


def bollinger(values: Sequence[float], period: int = 20, mult: float = 2.0) -> Tuple[List[Number], List[Number], List[Number]]:
    mid = sma(values, period)
    std = rolling_std(values, period)
    upper: List[Number] = [None] * len(values)
    lower: List[Number] = [None] * len(values)
    for i in range(len(values)):
        if mid[i] is not None and std[i] is not None:
            upper[i] = mid[i] + std[i] * mult
            lower[i] = mid[i] - std[i] * mult
    return mid, upper, lower


def dmi(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> Tuple[List[Number], List[Number], List[Number]]:
    n = len(closes)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = true_range(highs, lows, closes)

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm[i] = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm[i] = down_move if down_move > up_move and down_move > 0 else 0.0

    plus_di: List[Number] = [None] * n
    minus_di: List[Number] = [None] * n
    dx: List[Number] = [None] * n
    adx: List[Number] = [None] * n
    if n <= period:
        return plus_di, minus_di, adx

    sm_tr = sum(tr[1 : period + 1])
    sm_plus = sum(plus_dm[1 : period + 1])
    sm_minus = sum(minus_dm[1 : period + 1])

    for i in range(period, n):
        if i > period:
            sm_tr = sm_tr - sm_tr / period + tr[i]
            sm_plus = sm_plus - sm_plus / period + plus_dm[i]
            sm_minus = sm_minus - sm_minus / period + minus_dm[i]

        if sm_tr == 0:
            continue
        plus_di[i] = 100.0 * sm_plus / sm_tr
        minus_di[i] = 100.0 * sm_minus / sm_tr
        denom = plus_di[i] + minus_di[i]
        if denom:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / denom

    first_adx_idx = period * 2 - 1
    if n > first_adx_idx:
        first_dx = [value for value in dx[period : first_adx_idx + 1] if value is not None]
        if len(first_dx) == period:
            adx_value = sum(first_dx) / period
            adx[first_adx_idx] = adx_value
            for i in range(first_adx_idx + 1, n):
                if dx[i] is None:
                    continue
                adx_value = (adx_value * (period - 1) + dx[i]) / period
                adx[i] = adx_value
    return plus_di, minus_di, adx
