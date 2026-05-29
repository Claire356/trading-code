from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api._common import read_json, run_agent, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = read_json(self)
        send_json(self, {"ok": True, "result": run_agent(body)})
