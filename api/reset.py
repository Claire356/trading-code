from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api._common import STATE_PATH, load_runtime, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        _, _, store = load_runtime()
        store.reset()
        send_json(self, {"ok": True, "status": "reset", "state": str(STATE_PATH)})
