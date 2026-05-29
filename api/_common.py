from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from trading_agent.config import load_config
from trading_agent.runtime import PaperAgentRuntime, step_result_to_dict
from trading_agent.state import JsonStateStore


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "us_sample.json"
STATE_PATH = Path(os.environ.get("AGENT_STATE_PATH", "/tmp/demo_us_paper_agent.json"))


def load_runtime() -> Tuple[Any, PaperAgentRuntime, JsonStateStore]:
    config = load_config(str(DEFAULT_CONFIG))
    store = JsonStateStore(str(STATE_PATH), config)
    return config, PaperAgentRuntime(config, store), store


def send_json(handler, payload: Dict[str, Any], status: int = 200) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def read_json(handler) -> Dict[str, Any]:
    length = int(handler.headers.get("content-length", "0"))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def run_agent(body: Dict[str, Any]) -> Dict[str, Any]:
    from trading_agent.research import generate_trade_research, report_to_dict

    config, runtime, _ = load_runtime()
    result = runtime.run_once(allow_reprocess=bool(body.get("allow_reprocess", False)))
    payload = step_result_to_dict(result)
    payload["agent"] = "demo-us-paper-agent"
    payload["mode"] = "paper"
    payload["state"] = str(STATE_PATH)

    if body.get("with_research"):
        provider = body.get("provider", "both")
        research = generate_trade_research(
            config=config,
            step_payload=payload,
            include_claude=provider in {"claude", "both"},
            include_miromind=provider in {"miromind", "both"},
            tier=body.get("report_tier", "quick"),
        )
        payload["research"] = report_to_dict(research)

    return payload
