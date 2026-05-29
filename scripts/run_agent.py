from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = PROJECT_ROOT / "agents" / "demo_us_paper_agent.json"
sys.path.insert(0, str(PROJECT_ROOT))

from trading_agent.config import load_config
from trading_agent.env import load_dotenv
from trading_agent.research import generate_trade_research, report_to_dict
from trading_agent.runtime import PaperAgentRuntime, step_result_to_dict
from trading_agent.state import JsonStateStore


def main() -> None:
    load_dotenv(str(PROJECT_ROOT / ".env"))

    parser = argparse.ArgumentParser(description="Run a configured paper trading agent")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE), help="Agent profile JSON path")
    parser.add_argument("--reset", action="store_true", help="Reset the agent state before running")
    parser.add_argument("--allow-reprocess", action="store_true", help="Allow processing the latest bar again")
    parser.add_argument("--with-research", action="store_true", help="Call Claude and/or Miromind for a research report")
    parser.add_argument(
        "--research-provider",
        choices=["claude", "miromind", "both"],
        default="both",
        help="Provider to call when --with-research is set",
    )
    parser.add_argument("--json", action="store_true", help="Print raw JSON output")
    args = parser.parse_args()

    profile = _load_profile(Path(args.profile))
    config_path = _resolve_path(profile["config"])
    state_path = _resolve_path(profile["state"])
    config = load_config(str(config_path))

    if args.reset:
        JsonStateStore(str(state_path), config).reset()

    runtime = PaperAgentRuntime(config, JsonStateStore(str(state_path), config))
    result = runtime.run_once(allow_reprocess=args.allow_reprocess)
    payload = step_result_to_dict(result)
    payload["agent"] = profile["name"]
    payload["mode"] = profile.get("mode", "paper")
    payload["state"] = str(state_path)

    if args.with_research:
        research = generate_trade_research(
            config=config,
            step_payload=payload,
            include_claude=args.research_provider in {"claude", "both"},
            include_miromind=args.research_provider in {"miromind", "both"},
        )
        payload["research"] = report_to_dict(research)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_summary(payload)


def _load_profile(path: Path) -> Dict[str, Any]:
    profile_path = path if path.is_absolute() else PROJECT_ROOT / path
    return json.loads(profile_path.read_text(encoding="utf-8"))


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _print_summary(payload: Dict[str, Any]) -> None:
    print(f"Agent:  {payload['agent']} ({payload['mode']})")
    print(f"Symbol: {payload['symbol']}")
    print(f"Time:   {payload['timestamp']}")
    print(f"Action: {payload['action']}")
    print(f"Reason: {payload['reason']}")
    print(f"Equity: ${payload['equity_usd']:,.2f}")
    print(f"Cash:   ${payload['cash_usd']:,.2f}")

    order = payload.get("order")
    if order:
        print(f"Order:  {order}")

    fill = payload.get("fill")
    if fill:
        print(f"Fill:   {fill}")

    position = payload.get("position")
    if position:
        print(
            "Position: "
            f"{position['quantity']} shares @ {position['entry_price']:.2f}, "
            f"stop {position['active_stop']:.2f}, target {position['take_profit']:.2f}"
        )

    print(f"State:  {payload['state']}")

    research = payload.get("research")
    if research:
        if research.get("claude_review"):
            print("\nClaude Risk Review")
            print(research["claude_review"])
        if research.get("miromind_research"):
            print("\nMiromind Deep Research")
            print(research["miromind_research"])
        if research.get("errors"):
            print("\nResearch Errors")
            for provider, error in research["errors"].items():
                print(f"- {provider}: {error}")


if __name__ == "__main__":
    main()
