"""
LLM-as-judge pass: Claude scoring Claude's output on dimensions that
don't have a clean automatic ground truth -- overall answer quality,
whether the right tool(s) appear to have been used for the query type,
and whether the grounding check appears to have functioned correctly.

This is explicitly a *complement* to the precision/recall metrics in
metrics.py, not a replacement -- the harness reports both.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.agent.client import create_message_with_retry, get_client
from app.config import get_settings
from app.models.schemas import GroundingReport, NewsAnalysis
from eval.golden_dataset import GoldenCase

logger = logging.getLogger("market_pulse")

_JUDGE_SYSTEM_PROMPT = """You are an impartial evaluator judging the output of a market-news \
analysis agent. You will see: the case description, the tools that were called during the \
agent run, the agent's final structured output, and the result of a separate grounding \
verification pass.

Score each of the following on a 1-5 scale (5 = excellent):
- answer_quality: Is the summary clear, specific, and useful? Does it avoid vague filler?
- tool_appropriateness: Given the case, were sensible tools called (e.g. news search for a \
  news question, price history for a price question)? Penalize obviously missing or \
  superfluous tool calls.
- grounding_check_functioning: Based on what you see, does the grounding report look like it \
  did real verification work (plausible claims flagged or plausibly nothing to flag), as \
  opposed to a rubber-stamp "everything's fine" with no evidence of checking?

Respond with ONLY a JSON object of this exact form, no prose, no markdown fences:
{"answer_quality": <1-5>, "tool_appropriateness": <1-5>, "grounding_check_functioning": <1-5>, "justification": "<1-3 sentences>"}"""


@dataclass
class JudgeScore:
    case_id: str
    answer_quality: int
    tool_appropriateness: int
    grounding_check_functioning: int
    justification: str


def judge_case(
    case: GoldenCase,
    analysis: NewsAnalysis,
    grounding: GroundingReport,
    tool_names_called: list[str],
) -> JudgeScore:
    settings = get_settings()
    client = get_client()

    user_content = f"""Case description: {case.description}
Ticker: {case.ticker}

Tools called during this run: {tool_names_called}

Agent's final structured output:
{json.dumps(analysis.model_dump(), indent=2)}

Grounding verification result:
{json.dumps(grounding.model_dump(), indent=2)}"""

    try:
        response = create_message_with_retry(
            client,
            model=settings.judge_model,
            max_tokens=500,
            system=_JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
        return JudgeScore(
            case_id=case.case_id,
            answer_quality=int(parsed.get("answer_quality", 0)),
            tool_appropriateness=int(parsed.get("tool_appropriateness", 0)),
            grounding_check_functioning=int(parsed.get("grounding_check_functioning", 0)),
            justification=str(parsed.get("justification", "")),
        )
    except Exception as e:
        logger.warning(f"LLM judge failed for case {case.case_id}: {e}")
        return JudgeScore(
            case_id=case.case_id,
            answer_quality=0,
            tool_appropriateness=0,
            grounding_check_functioning=0,
            justification=f"judge call failed: {e}",
        )
