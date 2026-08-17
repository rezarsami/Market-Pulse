"""
Lightweight structured observability: one JSON line per span, written to
a local log file (and stdout). No hosted platform required, but the
schema is deliberately flat and consistent so it could be piped into
one (Honeycomb, Datadog, etc.) later with minimal transformation.

Two span types:
  - "request": one per top-level API call (POST /analyze)
  - "tool_call": one per tool invocation inside the agent loop

Both carry latency, and cost-relevant fields (tokens in/out, estimated
cost) where applicable.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

from app.config import get_settings

_settings = get_settings()
os.makedirs(_settings.log_dir, exist_ok=True)

_logger = logging.getLogger("market_pulse")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    file_handler = logging.FileHandler(
        os.path.join(_settings.log_dir, "structured.log.jsonl")
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(stream_handler)


def _cost_for_tokens(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price = _settings.price_per_1m_input_tokens.get(model, 3.0)
    out_price = _settings.price_per_1m_output_tokens.get(model, 15.0)
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price


def _cost_for_searches(n_searches: int) -> float:
    return (n_searches / 1000) * _settings.price_per_1k_web_searches


@dataclass
class Span:
    span_type: str
    name: str
    request_id: str
    start_ts: float = field(default_factory=time.time)
    extra: dict = field(default_factory=dict)

    def emit(self, **kwargs) -> None:
        end_ts = time.time()
        record = {
            "span_type": self.span_type,
            "name": self.name,
            "request_id": self.request_id,
            "timestamp": end_ts,
            "latency_ms": round((end_ts - self.start_ts) * 1000, 2),
            **self.extra,
            **kwargs,
        }
        _logger.info(json.dumps(record, default=str))


class RequestTracer:
    """
    Aggregates all spans for a single top-level request and provides
    running cost totals. One instance per POST /analyze call.
    """

    def __init__(self, request_id: str | None = None):
        self.request_id = request_id or str(uuid.uuid4())
        self._start = time.time()
        self.tool_calls: list[dict] = []
        self.model_calls: list[dict] = []
        self.total_cost_usd = 0.0

    @contextmanager
    def tool_span(self, tool_name: str, tool_input: dict):
        span = Span(span_type="tool_call", name=tool_name, request_id=self.request_id)
        result_holder: dict = {}
        try:
            yield result_holder
        finally:
            latency_ms = round((time.time() - span.start_ts) * 1000, 2)
            record = {
                "tool_name": tool_name,
                "input": tool_input,
                "latency_ms": latency_ms,
                "output_summary": result_holder.get("output_summary", ""),
                "error": result_holder.get("error"),
            }
            self.tool_calls.append(record)
            span.emit(**record)

    def log_model_call(
        self,
        model: str,
        purpose: str,
        input_tokens: int,
        output_tokens: int,
        web_searches: int = 0,
        latency_ms: float = 0.0,
    ) -> float:
        cost = _cost_for_tokens(model, input_tokens, output_tokens) + _cost_for_searches(
            web_searches
        )
        self.total_cost_usd += cost
        record = {
            "model": model,
            "purpose": purpose,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "web_searches": web_searches,
            "estimated_cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
        }
        self.model_calls.append(record)
        span = Span(span_type="model_call", name=purpose, request_id=self.request_id)
        span.emit(**record)
        return cost

    def finish(self, **extra) -> dict:
        total_latency_ms = round((time.time() - self._start) * 1000, 2)
        record = {
            "total_latency_ms": total_latency_ms,
            "total_estimated_cost_usd": round(self.total_cost_usd, 6),
            "num_tool_calls": len(self.tool_calls),
            "num_model_calls": len(self.model_calls),
            **extra,
        }
        span = Span(span_type="request", name="analyze", request_id=self.request_id)
        span.start_ts = self._start
        span.emit(**record)
        return record
