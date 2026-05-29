from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from .config import AgentConfig
from .llm import ClaudeClient, LLMError, MiroMindClient


@dataclass
class ResearchReport:
    tier: str = "medium"
    claude_review: Optional[str] = None
    miromind_research: Optional[str] = None
    investment_guidance: Optional[dict] = None
    errors: Dict[str, str] = field(default_factory=dict)


class ReportTier(str, Enum):
    QUICK = "quick"
    MEDIUM = "medium"
    DEEP = "deep"


def generate_trade_research(
    config: AgentConfig,
    step_payload: dict,
    include_claude: bool = True,
    include_miromind: bool = True,
    tier: str = ReportTier.MEDIUM.value,
) -> ResearchReport:
    report_tier = ReportTier(tier)
    if report_tier == ReportTier.QUICK:
        include_miromind = False

    report = ResearchReport(tier=report_tier.value)
    context = _build_context(config, step_payload)
    report.investment_guidance = _investment_guidance(config, step_payload, report_tier)

    if include_claude:
        try:
            report.claude_review = ClaudeClient().complete(
                prompt=_claude_prompt(context, report_tier),
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
        default_timeout = "120" if report_tier == ReportTier.DEEP else "45"
        miromind_timeout = int(os.environ.get("MIROMIND_TIMEOUT_SECONDS", default_timeout))
        miro = MiroMindClient(timeout=miromind_timeout)
        default_mode = "responses" if report_tier == ReportTier.DEEP else "chat"
        mode = os.environ.get("MIROMIND_RESEARCH_MODE", default_mode).lower()
        max_tokens = 2200 if report_tier == ReportTier.DEEP else 450
        if mode == "responses":
            try:
                report.miromind_research = miro.deep_research(
                    prompt=_miromind_prompt(context, report_tier),
                    max_output_tokens=max_tokens,
                    background=False,
                ).text
            except LLMError as exc:
                report.errors["miromind_responses_api"] = str(exc)
        if report.miromind_research is None:
            try:
                report.miromind_research = miro.chat(
                    [{"role": "user", "content": _miromind_prompt(context, report_tier)}],
                    max_tokens=max_tokens,
                ).text
            except LLMError as exc:
                report.errors["miromind_chat"] = str(exc)
            except Exception as exc:
                report.errors["miromind_chat"] = f"Unexpected error: {exc}"

    return report


def report_to_dict(report: ResearchReport) -> dict:
    return {
        "tier": report.tier,
        "claude_review": report.claude_review,
        "miromind_research": report.miromind_research,
        "investment_guidance": report.investment_guidance,
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


def _claude_prompt(context: str, tier: ReportTier) -> str:
    if tier == ReportTier.QUICK:
        instructions = """
Return a very concise Chinese report:
1. Rule signal summary.
2. Top 3 immediate risks.
3. Action label: observe / paper-only / review-before-real-order.
4. State clearly this is not investment advice.
""".strip()
    elif tier == ReportTier.MEDIUM:
        instructions = """
Return a concise Chinese report:
1. Rule signal summary.
2. Market/strategy risks.
3. Checks before any real order.
4. Suggested execution posture: observe / wait / paper-only / human-review.
5. State clearly this is not investment advice.
""".strip()
    else:
        instructions = """
Return a detailed Chinese risk memo:
1. Rule signal summary.
2. Strategy validity and market-regime risks.
3. Position sizing and execution risks.
4. Data gaps and checks before any real order.
5. Suggested execution posture: observe / wait / paper-only / human-review.
6. State clearly this is not investment advice.
""".strip()

    return f"""
Review this rule-based trading-agent step.

{context}

{instructions}
""".strip()


def _miromind_prompt(context: str, tier: ReportTier) -> str:
    if tier == ReportTier.DEEP:
        instructions = """
Return a structured Chinese deep research memo:
- Latest relevant company/market context if available
- Bullish factors with evidence
- Bearish factors with evidence
- Event/catalyst risks to check
- Liquidity, regulatory, and market-structure considerations
- Additional data needed before real trading
- Research conclusion separated from the rule-based action
""".strip()
    else:
        instructions = """
Return Chinese bullet points only:
- Bullish factors
- Bearish factors
- Event/catalyst risks to check
- Liquidity and market-structure considerations
- Additional data needed before real trading
Keep the whole answer under 250 Chinese characters.
""".strip()

    return f"""
Use the Miromind DeepResearch model to produce a market research brief for this trading-agent step.

{context}

{instructions}

Do not recommend automatic execution. Treat this as research support for a rule-based paper trading agent.
""".strip()


def _investment_guidance(config: AgentConfig, step_payload: dict, tier: ReportTier) -> dict:
    action = step_payload.get("action", "HOLD")
    reason = step_payload.get("reason", "")
    has_position = step_payload.get("position") is not None
    has_order = step_payload.get("order") is not None

    if action == "BUY":
        posture = "paper_or_human_review_before_real_order"
        rule_view = "规则策略出现做多信号。"
    elif action == "SELL":
        posture = "risk_exit_or_human_review"
        rule_view = "规则策略出现退出/卖出信号。"
    elif has_position:
        posture = "hold_and_monitor"
        rule_view = "规则策略当前持有仓位并继续监控。"
    else:
        posture = "observe"
        rule_view = "规则策略当前没有新交易动作。"

    if reason == "bar_already_processed":
        posture = "no_action_duplicate_bar"
        rule_view = "当前 K 线已经处理过，系统阻止重复下单。"

    research_depth = {
        ReportTier.QUICK: "快速报告：偏运行安全检查，不做外部深度研究。",
        ReportTier.MEDIUM: "中度报告：结合风险复核和简版市场研究。",
        ReportTier.DEEP: "深度报告：加入更长研究链路，适合重大交易前复核。",
    }[tier]

    return {
        "symbol": config.market.symbol,
        "market": config.market.market.value,
        "rule_action": action,
        "rule_reason": reason,
        "rule_view": rule_view,
        "execution_posture": posture,
        "research_depth": research_depth,
        "real_money_note": "这不是投资建议；真实下单前需要人工确认、检查实时行情、成本、流动性和账户持仓。",
        "order_present": has_order,
    }
