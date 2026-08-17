"""
Explicit router strategy: a fast, cheap classification step determines
query intent (news / price / calculation / mixed) before any tool
dispatch happens, as opposed to letting the model decide autonomously
turn by turn (the "agentic" strategy in loop.py).

Uses the small/cheap model (Haiku-class) with a constrained JSON output
so classification itself is fast and inexpensive.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Literal

from app.agent.client import create_message_with_retry, get_client
from app.config import get_settings
from app.observability.tracing import RequestTracer

logger = logging.getLogger("market_pulse")

Intent = Literal["news", "price", "calculation", "mixed"]

_ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a stock market assistant.
Given a ticker and an optional user question, classify the intent into exactly one of:
- "news": the user wants recent news / qualitative context on what might move the price
- "price": the user wants historical price/chart data only, no news needed
- "calculation": the user wants a numeric computation (e.g. % change) that needs price data plus arithmetic
- "mixed": the user wants a combination of news and price/calculation context

If there is no question (just a ticker), default to "mixed" since the app's
default view combines a news summary and a price chart.

Respond with ONLY a JSON object of the form:
{"intent": "<news|price|calculation|mixed>", "needs_price_history": true|false, "needs_news_search": true|false, "needs_calculation": true|false}
No prose, no markdown fences, just the JSON object."""


@dataclass
class RouteDecision:
    intent: Intent
    needs_price_history: bool
    needs_news_search: bool
    needs_calculation: bool
    raw_latency_ms: float


def route_query(ticker: str, question: str | None, tracer: RequestTracer) -> RouteDecision:
    settings = get_settings()
    client = get_client()

    user_content = f"Ticker: {ticker}\nQuestion: {question or '(none - default overview requested)'}"

    start = time.time()
    response = create_message_with_retry(
        client,
        model=settings.router_model,
        max_tokens=200,
        system=_ROUTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    latency_ms = round((time.time() - start) * 1000, 2)

    text = "".join(block.text for block in response.content if block.type == "text")

    tracer.log_model_call(
        model=settings.router_model,
        purpose="router_classification",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )

    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").lstrip("json").strip()
        parsed = json.loads(cleaned)
        intent = parsed.get("intent", "mixed")
        if intent not in ("news", "price", "calculation", "mixed"):
            intent = "mixed"
        return RouteDecision(
            intent=intent,
            needs_price_history=bool(parsed.get("needs_price_history", True)),
            needs_news_search=bool(parsed.get("needs_news_search", True)),
            needs_calculation=bool(parsed.get("needs_calculation", False)),
            raw_latency_ms=latency_ms,
        )
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Router classification failed to parse ({e}); defaulting to mixed")
        # Fail open to "mixed" -- the safest default that still gets the
        # user useful output rather than blocking the request.
        return RouteDecision(
            intent="mixed",
            needs_price_history=True,
            needs_news_search=True,
            needs_calculation=False,
            raw_latency_ms=latency_ms,
        )
