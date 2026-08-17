from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request

from app.agent.grounding import run_grounding_check
from app.agent.loop import run_agent
from app.config import get_settings
from app.guardrails.rate_limiter import RateLimiter
from app.guardrails.sanitize import sanitize_question, sanitize_ticker
from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CostBreakdown,
    ToolCallLog,
)
from app.observability.tracing import RequestTracer

logger = logging.getLogger("market_pulse")
router = APIRouter()

_settings = get_settings()
_rate_limiter = RateLimiter(
    per_minute=_settings.rate_limit_requests_per_minute,
    per_day=_settings.rate_limit_requests_per_day,
)


def _client_key(request: Request) -> str:
    # Prefer a session id header if the frontend sends one; fall back to
    # client IP. Either way this bounds spend per "user" for the demo.
    session_id = request.headers.get("x-session-id")
    if session_id:
        return f"session:{session_id}"
    if request.client:
        return f"ip:{request.client.host}"
    return "unknown"


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    settings = get_settings()

    decision = _rate_limiter.check_and_record(_client_key(request))
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": decision.reason,
                "retry_after_seconds": decision.retry_after_seconds,
            },
        )

    ticker_result = sanitize_ticker(payload.ticker)
    if not ticker_result.ok:
        raise HTTPException(status_code=400, detail=ticker_result.reason)

    question_result = sanitize_question(
        payload.question, max_length=settings.max_question_length
    )
    if not question_result.ok:
        raise HTTPException(status_code=400, detail=question_result.reason)

    request_id = str(uuid.uuid4())
    tracer = RequestTracer(request_id=request_id)

    try:
        agent_result = run_agent(
            ticker=ticker_result.cleaned,
            question=question_result.cleaned or None,
            tracer=tracer,
            strategy=payload.strategy_override,
        )
    except RuntimeError as e:
        # Missing API key etc.
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Agent run failed for ticker={ticker_result.cleaned}")
        raise HTTPException(status_code=502, detail=f"Agent run failed: {e}")

    grounding_report = run_grounding_check(agent_result.news_analysis, tracer)

    summary_record = tracer.finish(
        ticker=ticker_result.cleaned,
        strategy_used=agent_result.strategy_used,
        search_mode=agent_result.search_mode,
        schema_validation_retries=agent_result.schema_validation_retries,
        grounding_ok=grounding_report.is_fully_grounded,
    )

    cost_breakdown = [
        CostBreakdown(
            model=mc["model"],
            input_tokens=mc["input_tokens"],
            output_tokens=mc["output_tokens"],
            web_searches=mc["web_searches"],
            estimated_cost_usd=mc["estimated_cost_usd"],
        )
        for mc in tracer.model_calls
    ]

    tool_call_logs = [
        ToolCallLog(
            tool_name=tc["tool_name"],
            input=tc["input"],
            latency_ms=tc["latency_ms"],
            output_summary=tc["output_summary"],
        )
        for tc in tracer.tool_calls
    ]

    return AnalyzeResponse(
        ticker=ticker_result.cleaned,
        question=question_result.cleaned or None,
        strategy_used=agent_result.strategy_used,
        news_analysis=agent_result.news_analysis,
        grounding_report=grounding_report,
        schema_validation_retries=agent_result.schema_validation_retries,
        tool_calls=tool_call_logs,
        cost_breakdown=cost_breakdown,
        total_estimated_cost_usd=round(tracer.total_cost_usd, 6),
        total_latency_ms=summary_record["total_latency_ms"],
        request_id=request_id,
    )
