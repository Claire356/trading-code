from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path


def main() -> None:
    out = Path("data/sample_us.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    start = date(2024, 1, 2)
    rows = []
    price = 100.0
    trading_days = 0
    day = start
    while trading_days < 120:
        if day.weekday() < 5:
            drift = 0.35 if trading_days < 80 else -0.05
            wave = ((trading_days % 9) - 4) * 0.08
            open_price = price + wave
            close = open_price + drift + 0.18
            high = max(open_price, close) + 0.25
            low = min(open_price, close) - 0.25
            volume = 1_000_000 + (trading_days % 7) * 120_000
            rows.append(
                {
                    "timestamp": day.isoformat(),
                    "open": f"{open_price:.2f}",
                    "high": f"{high:.2f}",
                    "low": f"{low:.2f}",
                    "close": f"{close:.2f}",
                    "volume": str(volume),
                }
            )
            price = close
            trading_days += 1
        day += timedelta(days=1)

    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
