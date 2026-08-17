"""
Dispatches client tool calls (calculate, get_price_history, search_news
fallback) to their real implementations, wrapping each in a tracing span.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from app.guardrails.safe_calculator import safe_calculate
from app.observability.tracing import RequestTracer
from app.tools.fallback_search import fallback_search
from app.tools.price_history import get_price_history


def execute_client_tool(tool_name: str, tool_input: dict, tracer: RequestTracer) -> str:
    """
    Execute a client-side tool and return a JSON string suitable for a
    tool_result content block. Always returns *something* -- errors are
    serialized into the result rather than raised, so the agent loop can
    keep running and the model can see the failure and react to it.
    """
    with tracer.tool_span(tool_name, tool_input) as result_holder:
        try:
            if tool_name == "calculate":
                res = safe_calculate(tool_input.get("expression", ""))
                payload = asdict(res)
                result_holder["output_summary"] = (
                    f"result={res.value}" if res.ok else f"error={res.error}"
                )
                return json.dumps(payload)

            if tool_name == "get_price_history":
                res = get_price_history(
                    ticker=tool_input.get("ticker", ""),
                    period=tool_input.get("period", "1M"),
                )
                payload = {
                    "ticker": res.ticker,
                    "period": res.period,
                    "interval": res.interval,
                    "no_data_found": res.no_data_found,
                    "error": res.error,
                    "currency": res.currency,
                    # Trim bars sent back to the model -- it doesn't need
                    # every 5-minute bar to reason about a summary; give it
                    # first/last/high/low context plus a sample. Full data
                    # goes to the chart endpoint separately.
                    "num_bars": len(res.bars),
                    "first_bar": asdict(res.bars[0]) if res.bars else None,
                    "last_bar": asdict(res.bars[-1]) if res.bars else None,
                    "period_high": max((b.high for b in res.bars), default=None),
                    "period_low": min((b.low for b in res.bars), default=None),
                }
                result_holder["output_summary"] = (
                    "no_data_found"
                    if res.no_data_found
                    else f"{len(res.bars)} bars, {res.period}"
                )
                if res.no_data_found:
                    result_holder["error"] = res.error or "no data found"
                return json.dumps(payload)

            if tool_name == "search_news":
                res = fallback_search(
                    query=tool_input.get("query", tool_input.get("ticker", ""))
                )
                payload = {
                    "query": res.query,
                    "provider": res.provider,
                    "error": res.error,
                    "results": [
                        {
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "published_at": r.published_at,
                        }
                        for r in res.results
                    ],
                }
                result_holder["output_summary"] = (
                    f"{len(res.results)} results via {res.provider}"
                    if not res.error
                    else f"error={res.error}"
                )
                if res.error:
                    result_holder["error"] = res.error
                return json.dumps(payload)

            result_holder["error"] = f"unknown tool: {tool_name}"
            return json.dumps({"error": f"unknown tool: {tool_name}"})

        except Exception as e:  # never let a tool crash the agent loop
            result_holder["error"] = str(e)
            return json.dumps({"error": f"tool execution failed: {e}"})
