"""
Grounding / verification pass.

After the agent produces its final NewsAnalysis, we run a separate,
cheaper model call whose only job is to check whether each factual claim
in `summary` (and in each item's `rationale`) is actually supported by
the news items the agent itself surfaced (headline/source/url/rationale
pairs -- the closest thing we have to "the retrieved evidence" once the
tool loop has finished). Any claim that isn't traceable to that evidence
is flagged, not silently trusted.

This is a real implementation of the technique, not a comment -- it
makes an actual second API call and parses actual structured output.
"""
from __future__ import annotations

import json
import logging
import time

from pydantic import ValidationError

from app.agent.client import create_message_with_retry, get_client
from app.config import get_settings
from app.models.schemas import GroundingFlag, GroundingReport, NewsAnalysis
from app.observability.tracing import RequestTracer

logger = logging.getLogger("market_pulse")

_GROUNDING_SYSTEM_PROMPT = """You are a fact-checking verifier for a financial news summary. \
You will be given:
1. A list of "evidence" items (news headlines, sources, urls, and rationales that \
   an upstream agent claims it found via web search)
2. A "summary" paragraph that synthesizes those items
3. Optionally, a list of "materiality" judgments: each names a specific headline the \
   agent found and assigns it a relative weight (high/medium/routine) with a short \
   reason.

Your job has two parts:

A) SUMMARY: identify any claim in the summary that is NOT supported by the evidence \
items. A claim is unsupported if it states a specific fact (a number, an event, an \
attribution, a date, a causal claim) that doesn't appear in any evidence item's \
headline or rationale. General synthesis language ("this suggests", "overall") is \
fine and doesn't need to be flagged.

B) MATERIALITY: for each materiality judgment, flag it if EITHER (i) its "headline" \
does not match any evidence item's headline (the agent referenced something it didn't \
actually find), OR (ii) its "why" introduces a specific fact not present in that \
item's headline or rationale. Do NOT flag the weight itself (high/medium/routine is a \
subjective ranking, not a factual claim) -- only flag fabricated headlines or invented \
supporting facts.

Count every summary claim AND every materiality judgment you examine toward \
checked_claims. When you flag a materiality problem, prefix the claim text with \
"[materiality] " so it's distinguishable.

Respond with ONLY a JSON object of this exact form, no prose, no markdown fences:
{
  "is_fully_grounded": true|false,
  "checked_claims": <integer, roughly how many distinct factual claims + materiality judgments you checked>,
  "flagged_claims": [
    {"claim": "<the unsupported claim, quoted or closely paraphrased>",
     "reason": "<why it isn't supported by the evidence>"}
  ]
}
If everything is grounded, return an empty flagged_claims list and is_fully_grounded: true."""


def run_grounding_check(
    news_analysis: NewsAnalysis, tracer: RequestTracer
) -> GroundingReport:
    settings = get_settings()

    if news_analysis.no_data_found or not news_analysis.items:
        # Nothing to ground against; a "no data found" statement is
        # trivially grounded (it's a statement about absence, not a
        # specific factual claim that needs evidence).
        return GroundingReport(is_fully_grounded=True, checked_claims=0, flagged_claims=[])

    evidence = [
        {
            "headline": item.headline,
            "source": item.source,
            "url": item.url,
            "published_at": item.published_at,
            "rationale": item.rationale,
        }
        for item in news_analysis.items
    ]

    user_content = (
        f"Evidence items:\n{json.dumps(evidence, indent=2)}\n\n"
        f"Summary to verify:\n{news_analysis.summary}"
    )

    if news_analysis.materiality:
        materiality_payload = [
            {"headline": m.headline, "weight": m.weight, "why": m.why}
            for m in news_analysis.materiality
        ]
        user_content += (
            f"\n\nMateriality judgments to verify:\n"
            f"{json.dumps(materiality_payload, indent=2)}"
        )

    client = get_client()
    start = time.time()
    try:
        response = create_message_with_retry(
            client,
            model=settings.grounding_model,
            max_tokens=1000,
            system=_GROUNDING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as e:
        logger.error(f"Grounding check API call failed: {e}")
        # Fail safe: don't silently claim grounded if we couldn't check.
        return GroundingReport(
            is_fully_grounded=False,
            checked_claims=0,
            flagged_claims=[
                GroundingFlag(
                    claim="(grounding check itself failed)",
                    reason=f"verifier call errored: {e}",
                )
            ],
        )
    latency_ms = round((time.time() - start) * 1000, 2)

    tracer.log_model_call(
        model=settings.grounding_model,
        purpose="grounding_check",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
        return GroundingReport.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"Grounding report failed to parse: {e}. Raw: {text[:500]}")
        return GroundingReport(
            is_fully_grounded=False,
            checked_claims=0,
            flagged_claims=[
                GroundingFlag(
                    claim="(could not parse grounding verifier output)",
                    reason=str(e),
                )
            ],
        )
