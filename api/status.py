from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler

from api._common import STATE_PATH, load_runtime, send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        config, _, store = load_runtime()
        state = store.load()
        send_json(
            self,
            {
                "ok": True,
                "agent": "demo-us-paper-agent",
                "mode": "paper",
                "symbol": config.market.symbol,
                "market": config.market.market.value,
                "currency": config.market.currency,
                "state_path": str(STATE_PATH),
                "has_position": state.position is not None,
                "last_bar_timestamp": state.last_bar_timestamp,
                "keys": {
                    "claude": bool(os.environ.get("ANTHROPIC_API_KEY")),
                    "miromind": bool(os.environ.get("MIROMIND_API_KEY")),
                },
            },
        )
