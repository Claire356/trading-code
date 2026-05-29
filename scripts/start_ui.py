from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
DEFAULT_PROFILE = PROJECT_ROOT / "agents" / "demo_us_paper_agent.json"
sys.path.insert(0, str(PROJECT_ROOT))

from trading_agent.config import load_config
from trading_agent.data import load_bars
from trading_agent.env import load_dotenv
from trading_agent.research import generate_trade_research, report_to_dict
from trading_agent.runtime import PaperAgentRuntime, step_result_to_dict
from trading_agent.state import JsonStateStore


class AgentUIHandler(SimpleHTTPRequestHandler):
    profile_path = DEFAULT_PROFILE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(status_payload(self.profile_path))
            return
        if parsed.path == "/api/bars":
            self._send_json(bars_payload(self.profile_path))
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/run":
                body = self._read_json()
                self._send_json(run_agent_payload(self.profile_path, body))
                return
            if parsed.path == "/api/reset":
                self._send_json(reset_payload(self.profile_path))
                return
            self.send_error(404, "Unknown endpoint")
        except Exception as exc:
            traceback.print_exc()
            self._send_json({"ok": False, "error": str(exc)}, status=500)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[ui] {self.address_string()} - {fmt % args}")

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local trading agent web UI")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    load_dotenv(str(PROJECT_ROOT / ".env"))
    AgentUIHandler.profile_path = _resolve_path(args.profile)

    server = ThreadingHTTPServer((args.host, args.port), AgentUIHandler)
    print(f"Trading agent UI: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def status_payload(profile_path: Path) -> Dict[str, Any]:
    profile, config, state_path = load_profile_bundle(profile_path)
    state = JsonStateStore(str(state_path), config).load()
    return {
        "ok": True,
        "agent": profile.get("name"),
        "mode": profile.get("mode", "paper"),
        "symbol": config.market.symbol,
        "market": config.market.market.value,
        "currency": config.market.currency,
        "state_path": str(state_path),
        "has_position": state.position is not None,
        "last_bar_timestamp": state.last_bar_timestamp,
        "keys": {
            "claude": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "miromind": bool(os.environ.get("MIROMIND_API_KEY")),
        },
    }


def bars_payload(profile_path: Path) -> Dict[str, Any]:
    _, config, _ = load_profile_bundle(profile_path)
    bars = load_bars(config.data.bars_csv)
    recent = bars[-90:]
    return {
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
            for bar in recent
        ],
    }


def run_agent_payload(profile_path: Path, body: Dict[str, Any]) -> Dict[str, Any]:
    profile, config, state_path = load_profile_bundle(profile_path)
    allow_reprocess = bool(body.get("allow_reprocess", False))
    with_research = bool(body.get("with_research", False))
    report_tier = body.get("report_tier", "quick")
    provider = body.get("provider", "both")

    runtime = PaperAgentRuntime(config, JsonStateStore(str(state_path), config))
    result = runtime.run_once(allow_reprocess=allow_reprocess)
    payload = step_result_to_dict(result)
    payload["agent"] = profile.get("name")
    payload["mode"] = profile.get("mode", "paper")
    payload["state"] = str(state_path)

    if with_research:
        research = generate_trade_research(
            config=config,
            step_payload=payload,
            include_claude=provider in {"claude", "both"},
            include_miromind=provider in {"miromind", "both"},
            tier=report_tier,
        )
        payload["research"] = report_to_dict(research)

    return {"ok": True, "result": payload}


def reset_payload(profile_path: Path) -> Dict[str, Any]:
    _, config, state_path = load_profile_bundle(profile_path)
    JsonStateStore(str(state_path), config).reset()
    return {"ok": True, "status": "reset", "state": str(state_path)}


def load_profile_bundle(profile_path: Path):
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    config = load_config(str(_resolve_path(profile["config"])))
    state_path = _resolve_path(profile["state"])
    return profile, config, state_path


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    main()
