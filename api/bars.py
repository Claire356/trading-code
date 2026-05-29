from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api._common import load_runtime, send_json
from trading_agent.data import load_bars


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        config, _, _ = load_runtime()
        bars = load_bars(config.data.bars_csv)[-90:]
        send_json(
            self,
            {
                "ok": True,
                "bars": [
                    {
                        "timestamp": bar.timestamp.isoformat(),
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    }
                    for bar in bars
                ],
            },
        )
