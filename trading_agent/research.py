from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from .config import AgentConfig
from .llm import ClaudeClient, LLMError, MiroMindClient


@dataclass
class ResearchReport:
    claude_review: Optional[str] = None
    miromind_research: Optional[str] = None
    errors: Dict[str, str] = field(default_factory=dict)


def generate_trade_research(
    config: AgentConfig,
    step_payload: dict,
    include_claude: bool = True,
    include_miromind: bool = True,
) -> ResearchReport:
    report = ResearchReport()
    context = _build_context(config, step_payload)

    if include_claude:
        try:
            report.claude_review = ClaudeClient().complete(
                prompt=_claude_prompt(context),
                system=(
                    "You are a conservative trading risk reviewer. "
                    "Do not give personalized financial advice. "
                    "Do not override the rule-based strategy. "
                    "Focus on risks, missing checks, and operational cautions."
                ),
                max_tokens=1200,
            ).text
        except LLMError as exc:
            report.errors["claude"] = str(exc)
        except Exception as exc:
            report.errors["claude"] = f"Unexpected error: {exc}"

    if include_miromind:
        miromind_timeout = int(os.environ.get("MIROMIND_TIMEOUT_SECONDS", "45"))
        miro = MiroMindClient(timeout=miromind_timeout)
        mode = os.environ.get("MIROMIND_RESEARCH_MODE", "chat").lower()
        if mode == "responses":
            try:
                report.miromind_research = miro.deep_research(
                    prompt=_miromind_prompt(context),
                    max_output_tokens=900,
                    background=False,
                ).text
            except LLMError as exc:
                report.errors["miromind_responses_api"] = str(exc)
        if report.miromind_research is None:
            try:
                report.miromind_research = miro.chat(
                    [{"role": "user", "content": _miromind_prompt(context)}],
                    max_tokens=900,
                ).text
            except LLMError as exc:
                report.errors["miromind_chat"] = str(exc)
            except Exception as exc:
                report.errors["miromind_chat"] = f"Unexpected error: {exc}"

    return report


def report_to_dict(report: ResearchReport) -> dict:
    return {
        "claude_review": report.claude_review,
        "miromind_research": report.miromind_research,
        "errors": report.errors,
    }


def _build_context(config: AgentConfig, step_payload: dict) -> str:
    position = step_payload.get("position")
    order = step_payload.get("order")
    fill = step_payload.get("fill")
    details = step_payload.get("details", {})
    return f"""
Symbol: {config.market.symbol}
Market: {config.market.market.value}
Currency: {config.market.currency}
Agent action: {step_payload.get("action")}
Reason: {step_payload.get("reason")}
Timestamp: {step_payload.get("timestamp")}
Equity USD: {step_payload.get("equity_usd")}
Cash USD: {step_payload.get("cash_usd")}
Order: {order}
Fill: {fill}
Position: {position}
Strategy details: {details}
Risk config:
- risk_per_trade_pct={config.risk.risk_per_trade_pct}
- max_position_pct={config.risk.max_position_pct}
- max_daily_loss_pct={config.risk.max_daily_loss_pct}
- atr_stop_mult={config.risk.atr_stop_mult}
- reward_r={config.risk.reward_r}
""".strip()


def _claude_prompt(context: str) -> str:
    return f"""
Review this rule-based trading-agent step.

{context}

Return a concise Chinese report with:
1. Whether the action is operationally safe to consider.
2. Main market/strategy risks.
3. Checks I should do before any real order.
4. A clear reminder that this is not investment advice.
""".strip()


def _miromind_prompt(context: str) -> str:
    return f"""
Use the Miromind DeepResearch model to produce a concise market research brief for this trading-agent step.

{context}

Return Chinese bullet points only:
- Bullish factors
- Bearish factors
- Event/catalyst risks to check
- Liquidity and market-structure considerations
- Additional data needed before real trading

Do not recommend automatic execution. Treat this as research support for a rule-based paper trading agent.
""".strip()
