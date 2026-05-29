from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from trading_agent.env import load_dotenv
from trading_agent.llm import ClaudeClient, LLMError, MiroMindClient


def main() -> None:
    load_dotenv(str(PROJECT_ROOT / ".env"))

    parser = argparse.ArgumentParser(description="Check Claude and Miromind API connectivity")
    parser.add_argument("--provider", choices=["claude", "miromind", "both"], default="both")
    args = parser.parse_args()

    results = {}
    if args.provider in {"claude", "both"}:
        results["claude"] = _check_claude()
    if args.provider in {"miromind", "both"}:
        results["miromind"] = _check_miromind()
    print(json.dumps(results, indent=2, ensure_ascii=False))


def _check_claude() -> dict:
    try:
        text = ClaudeClient(timeout=60).complete(
            "Reply with exactly: claude ok",
            max_tokens=20,
        ).text
        return {"ok": True, "response": text}
    except LLMError as exc:
        return {"ok": False, "error": str(exc)}


def _check_miromind() -> dict:
    try:
        text = MiroMindClient(timeout=120).chat(
            [{"role": "user", "content": "Reply with exactly: miromind ok"}],
            max_tokens=30,
        ).text
        return {"ok": True, "response": text}
    except LLMError as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    main()
