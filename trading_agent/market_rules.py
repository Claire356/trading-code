from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from .config import MarketConfig
from .models import Market


MARKET_TIMEZONES = {
    Market.US: "America/New_York",
    Market.A_SHARES: "Asia/Shanghai",
    Market.HK: "Asia/Hong_Kong",
}


def local_dt(dt: datetime, market: Market) -> datetime:
    zone = ZoneInfo(MARKET_TIMEZONES[market])
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone)
    return dt.astimezone(zone)


def local_date(dt: datetime, market: Market):
    return local_dt(dt, market).date()


def is_regular_session(dt: datetime, market_cfg: MarketConfig) -> bool:
    if not market_cfg.use_session_filter:
        return True

    local = local_dt(dt, market_cfg.market)
    if local.weekday() >= 5:
        return False

    # Daily CSV bars often use midnight timestamps. Treat those as regular
    # session summaries rather than rejecting the entire daily backtest.
    if local.time() == time(0, 0):
        return True

    t = local.time()
    if market_cfg.market == Market.US:
        return time(9, 30) <= t <= time(16, 0)
    if market_cfg.market == Market.A_SHARES:
        return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(14, 57))
    if market_cfg.market == Market.HK:
        return (time(9, 30) <= t <= time(12, 0)) or (time(13, 0) <= t <= time(16, 0))
    return True


def is_t1_locked(entry_time: datetime, current_time: datetime, market_cfg: MarketConfig) -> bool:
    if market_cfg.market != Market.A_SHARES or not market_cfg.enforce_t1:
        return False
    return local_date(entry_time, market_cfg.market) >= local_date(current_time, market_cfg.market)
