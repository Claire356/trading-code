from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Bar


TIMESTAMP_COLUMNS = ("timestamp", "datetime", "date", "time")


def load_bars(path: str) -> List[Bar]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        bars = [_row_to_bar(row) for row in reader]
    bars.sort(key=lambda bar: bar.timestamp)
    return bars


def align_benchmark(symbol_bars: List[Bar], benchmark_bars: Optional[List[Bar]]) -> List[Optional[Bar]]:
    if not benchmark_bars:
        return [None] * len(symbol_bars)

    by_time: Dict[datetime, Bar] = {bar.timestamp: bar for bar in benchmark_bars}
    aligned: List[Optional[Bar]] = []
    last_seen: Optional[Bar] = None
    benchmark_iter = iter(sorted(benchmark_bars, key=lambda bar: bar.timestamp))
    current = next(benchmark_iter, None)

    for bar in symbol_bars:
        exact = by_time.get(bar.timestamp)
        if exact is not None:
            last_seen = exact
            aligned.append(exact)
            continue
        while current is not None and current.timestamp <= bar.timestamp:
            last_seen = current
            current = next(benchmark_iter, None)
        aligned.append(last_seen)
    return aligned


def write_trades_csv(path: str, rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return
    csv_path = Path(path)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _row_to_bar(row: Dict[str, str]) -> Bar:
    normalized = {key.strip().lower(): value for key, value in row.items()}
    ts_value = None
    for column in TIMESTAMP_COLUMNS:
        if column in normalized:
            ts_value = normalized[column]
            break
    if ts_value is None:
        raise ValueError("CSV must contain one of: timestamp, datetime, date, time")

    return Bar(
        timestamp=_parse_timestamp(ts_value),
        open=float(normalized["open"]),
        high=float(normalized["high"]),
        low=float(normalized["low"]),
        close=float(normalized["close"]),
        volume=float(normalized.get("volume", 0.0) or 0.0),
    )


def _parse_timestamp(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
