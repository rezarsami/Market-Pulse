"""
The hand-rolled agent loop. No LangChain or other framework -- this is a
direct implementation against the Anthropic Messages API's native tool-use
support, because for a single agent with three tools a framework adds
indirection without buying anything.

Two tool-selection strategies, chosen via config/request override:

  (a) "agentic": the model decides autonomously, turn by turn, which
      tool(s) to call based on the system prompt and conversation. We just
      keep looping until it stops requesting tools.

  (b) "router": app/agent/router.py runs a fast/cheap classification pass
      first (news / price / calculation / mixed) and we use that to decide
      up front which tools to make available / pre-fetch, then hand off to
      a (usually shorter) agentic loop with a narrower tool set and a
      system prompt that already states what was found.

Both strategies converge on the same structured-output step: after the
loop ends, we ask the model to emit a NewsAnalysis JSON object, validate
it against the Pydantic schema, and retry once with the validation error
fed back if it fails.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from app.agent.client import create_message_with_retry, get_client
from app.agent.executor import execute_client_tool
from app.agent.router import route_query
from app.config import get_settings
from app.models.schemas import NewsAnalysis
from app.observability.tracing import RequestTracer
from app.tools.definitions import (
    ALL_CLIENT_TOOLS_FALLBACK_SEARCH,
    ALL_CLIENT_TOOLS_NATIVE_SEARCH,
    CALCULATE_TOOL,
    GET_PRICE_HISTORY_TOOL,
    NATIVE_WEB_SEARCH_TOOL,
    SEARCH_NEWS_FALLBACK_TOOL,
)

logger = logging.getLogger("market_pulse")

_MAX_AGENT_TURNS = 8
_MAX_STRUCTURED_OUTPUT_RETRIES = 1

Strategy = Literal["agentic", "router"]


def _search_available(settings) -> tuple[bool, str]:
    """
    Returns (use_native, mode_description). We prefer native web search
    unless FORCE_FALLBACK_SEARCH is set (useful for testing the fallback
    path / demoing both architectures) or no Anthropic key is usable.
    Availability of the native tool itself is only truly known once we
    call the API; if it 400s as disabled, callers should catch that and
    re-invoke with fallback -- handled in run_agent().
    """
    if settings.force_fallback_search:
        return False, "fallback (forced via FORCE_FALLBACK_SEARCH)"
    return True, "native (web_search_20250305)"


_BASE_SYSTEM_PROMPT = """You are Market Pulse, a market intelligence agent. Given a stock/ETF \
ticker (and optionally a free-text question), you investigate what recent \
news could plausibly move its price, and you can pull historical price \
data and do arithmetic to support your analysis.

Rules you must follow:
1. Only report news you actually found via search. NEVER fabricate a \
headline, source, date, or fact. If you find no material news, say so \
plainly -- do not invent something to fill space.
2. If a tool returns "no data found" (e.g. an invalid/delisted ticker), \
report that plainly. Do not guess at a plausible-sounding answer instead.
3. Every news item you report must be traceable to an actual search \
result: real url, real source, real headline.
4. Use the calculate tool for any arithmetic (percent changes, ratios) \
instead of computing it yourself in text -- it's more reliable.
5. Be concise. Prioritize the 3-6 most material news items over an \
exhaustive list.

After you have gathered what you need, you will be asked to produce a \
final structured JSON summary -- so make sure your investigation actually \
surfaces headline, source, url, and publish date for each relevant item, \
since you'll need to cite them precisely."""


_STRUCTURED_OUTPUT_INSTRUCTION = """Now produce your final answer as a single JSON object -- \
and ONLY a JSON object, no prose, no markdown fences -- matching exactly this schema:

{{
  "ticker": "<ticker>",
  "items": [
    {{
      "headline": "<exact headline text>",
      "source": "<publication/site name>",
      "url": "<the exact url from search results>",
      "published_at": "<date/time as reported, best effort>",
      "relevance_score": <integer 1-5, 5=highly material>,
      "impact_direction": "<positive|negative|neutral|mixed>",
      "rationale": "<1-2 sentences referencing something SPECIFIC from the article>"
    }}
  ],
  "summary": "<2-4 sentence synthesized narrative across all items>",
  "no_data_found": <true if you found no material news, else false>
}}

Only include items you actually found via search with real urls. If you found \
nothing material, return an empty items list, no_data_found: true, and a summary \
saying plainly that no material recent news was found for {ticker}."""


@dataclass
class AgentRunResult:
    news_analysis: NewsAnalysis
    schema_validation_retries: int
    strategy_used: Strategy
    search_mode: str
    raw_final_text: str
    price_history_prefetched: dict | None = None


def _build_tools(use_native_search: bool, needs_price: bool, needs_calc: bool) -> list[dict]:
    tools: list[dict] = []
    if use_native_search:
        tools.append(NATIVE_WEB_SEARCH_TOOL)
    else:
        tools.append(SEARCH_NEWS_FALLBACK_TOOL)
    if needs_price:
        tools.append(GET_PRICE_HISTORY_TOOL)
    if needs_calc:
        tools.append(CALCULATE_TOOL)
    return tools


def _run_tool_loop(
    client,
    model: str,
    system_prompt: str,
    tools: list[dict],
    initial_user_message: str,
    tracer: RequestTracer,
    use_native_search: bool,
) -> list[dict]:
    """
    Runs the turn-by-turn tool loop until the model stops requesting
    tools or we hit the turn cap. Returns the full message history
    (list of {role, content}) so the caller can append the structured
    output request as a final turn.
    """
    messages: list[dict] = [{"role": "user", "content": initial_user_message}]

    for turn in range(_MAX_AGENT_TURNS):
        start = time.time()
        response = create_message_with_retry(
            client,
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )
        latency_ms = round((time.time() - start) * 1000, 2)

        web_searches = getattr(response.usage, "server_tool_use", None)
        n_searches = 0
        if web_searches is not None:
            n_searches = getattr(web_searches, "web_search_requests", 0) or 0

        tracer.log_model_call(
            model=model,
            purpose=f"agent_turn_{turn}",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            web_searches=n_searches,
            latency_ms=latency_ms,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            # Model is done calling tools (may have produced text, or
            # paused for another reason). Break out; caller decides what
            # to do next.
            break

        # Execute every client tool_use block; server tool_use blocks
        # (web_search) are handled by the API itself and don't need a
        # tool_result from us.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if use_native_search and block.name == "web_search":
                continue  # server tool, no client-side result needed
            result_json = execute_client_tool(block.name, block.input, tracer)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                }
            )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            # Only server tools were called (native search); the API
            # already resolved them inline, so if stop_reason was
            # tool_use but we produced no client results, avoid an
            # infinite loop by breaking.
            if all(
                (b.type == "tool_use" and use_native_search and b.name == "web_search")
                for b in response.content
                if b.type == "tool_use"
            ):
                continue  # let the loop re-call; API already advanced state
            break

    return messages


def _extract_text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


def _request_structured_output(
    client, model: str, system_prompt: str, messages: list[dict], ticker: str, tracer: RequestTracer
) -> tuple[NewsAnalysis, int, str]:
    """
    Ask the model to emit the final structured JSON, validate against
    NewsAnalysis, and retry once with the validation error fed back if
    it fails. Returns (parsed_model, num_retries, raw_text_of_final_attempt).
    """
    settings = get_settings()
    working_messages = list(messages)
    working_messages.append(
        {
            "role": "user",
            "content": _STRUCTURED_OUTPUT_INSTRUCTION.format(ticker=ticker),
        }
    )

    retries = 0
    last_raw_text = ""
    last_error: str | None = None

    for attempt in range(_MAX_STRUCTURED_OUTPUT_RETRIES + 1):
        start = time.time()
        response = create_message_with_retry(
            client,
            model=model,
            max_tokens=3000,
            system=system_prompt,
            messages=working_messages,
        )
        latency_ms = round((time.time() - start) * 1000, 2)
        text = _extract_text(response)
        last_raw_text = text

        tracer.log_model_call(
            model=model,
            purpose=f"structured_output_attempt_{attempt}",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
        )

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            parsed_json = json.loads(cleaned)
            model_obj = NewsAnalysis.model_validate(parsed_json)
            return model_obj, retries, text
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            logger.warning(
                f"Structured output validation failed (attempt {attempt + 1}): {e}"
            )
            if attempt < _MAX_STRUCTURED_OUTPUT_RETRIES:
                retries += 1
                working_messages.append({"role": "assistant", "content": text})
                working_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "That response failed schema validation with this error:\n"
                            f"{last_error}\n\n"
                            "Please respond again with ONLY a corrected JSON object matching "
                            "the exact schema described earlier. No prose, no markdown fences."
                        ),
                    }
                )

    # Exhausted retries -- surface a degraded-but-honest response rather
    # than crashing the request.
    degraded = NewsAnalysis(
        ticker=ticker,
        items=[],
        summary=(
            "The agent's output could not be parsed into the required structured "
            f"format after {retries + 1} attempt(s). Validation error: {last_error}. "
            "Raw model output has been logged for debugging."
        ),
        no_data_found=True,
    )
    logger.error(
        f"Structured output failed after all retries for ticker={ticker}: {last_error}\n"
        f"Raw text: {last_raw_text[:2000]}"
    )
    return degraded, retries, last_raw_text


def run_agent(
    ticker: str,
    question: str | None,
    tracer: RequestTracer,
    strategy: Strategy | None = None,
) -> AgentRunResult:
    settings = get_settings()
    strategy = strategy or settings.tool_strategy  # type: ignore[assignment]
    client = get_client()
    use_native_search, search_mode = _search_available(settings)

    if strategy == "router":
        decision = route_query(ticker, question, tracer)
        needs_price = decision.needs_price_history
        needs_calc = decision.needs_calculation
        needs_news = decision.needs_news_search
        intent_note = (
            f"[Router classified intent as '{decision.intent}': "
            f"news={needs_news}, price={needs_price}, calc={needs_calc}]"
        )
    else:
        # Pure agentic: give it everything and let it decide.
        needs_price, needs_calc, needs_news = True, True, True
        intent_note = "[Agentic strategy: model selects tools autonomously]"

    tools = _build_tools(use_native_search, needs_price=needs_price, needs_calc=needs_calc)
    if not needs_news:
        # Router decided news isn't needed (pure price/calc query) -- drop
        # the search tool entirely so the model can't wander into it.
        tools = [t for t in tools if t.get("name") not in ("web_search", "search_news") and t.get("type") != "web_search_20250305"]

    user_question_part = f"\n\nUser's specific question: {question}" if question else ""
    initial_message = (
        f"Analyze ticker: {ticker}{user_question_part}\n\n"
        f"{intent_note}\n\n"
        "Investigate recent news that could plausibly move this ticker's price. "
        "Use your tools as needed, then I will ask you for a final structured summary."
    )

    try:
        messages = _run_tool_loop(
            client,
            model=settings.agent_model,
            system_prompt=_BASE_SYSTEM_PROMPT,
            tools=tools,
            initial_user_message=initial_message,
            tracer=tracer,
            use_native_search=use_native_search,
        )
    except Exception as e:
        # If native web search is disabled for this org/key, the API
        # returns a 400 invalid_request_error. Fall back automatically.
        if use_native_search and "web search" in str(e).lower():
            logger.warning(
                f"Native web search unavailable ({e}); falling back to Tavily/Exa."
            )
            use_native_search = False
            search_mode = "fallback (native web_search unavailable on this API key)"
            tools = _build_tools(False, needs_price=needs_price, needs_calc=needs_calc)
            messages = _run_tool_loop(
                client,
                model=settings.agent_model,
                system_prompt=_BASE_SYSTEM_PROMPT,
                tools=tools,
                initial_user_message=initial_message,
                tracer=tracer,
                use_native_search=False,
            )
        else:
            raise

    news_analysis, retries, raw_text = _request_structured_output(
        client, settings.agent_model, _BASE_SYSTEM_PROMPT, messages, ticker, tracer
    )

    return AgentRunResult(
        news_analysis=news_analysis,
        schema_validation_retries=retries,
        strategy_used=strategy,  # type: ignore[arg-type]
        search_mode=search_mode,
        raw_final_text=raw_text,
    )
