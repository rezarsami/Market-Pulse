"""
Tests for the "validate, retry once with the error fed back, else degrade
gracefully" logic in app.agent.loop._request_structured_output.

We mock create_message_with_retry so no real API calls are made; the
tests verify the *control flow* (retry happens exactly once on failure,
succeeds if the second attempt is valid, degrades gracefully if both
attempts fail) independent of the LLM actually being called.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.agent.loop import _request_structured_output
from app.observability.tracing import RequestTracer


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _fake_response(text: str, input_tokens=100, output_tokens=50):
    return SimpleNamespace(
        content=[_text_block(text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason="end_turn",
    )


VALID_JSON = json.dumps(
    {
        "ticker": "AAPL",
        "items": [
            {
                "headline": "Apple Reports Record Q3 Revenue",
                "source": "Reuters",
                "url": "https://reuters.com/aapl-q3",
                "published_at": "2026-08-10",
                "relevance_score": 5,
                "impact_direction": "positive",
                "rationale": "Revenue exceeded guidance by 6% on strong services growth.",
            }
        ],
        "summary": "Apple beat expectations driven by services growth.",
        "no_data_found": False,
    }
)

INVALID_JSON_BAD_SCHEMA = json.dumps(
    {
        "ticker": "AAPL",
        "items": [
            {
                "headline": "Apple Reports Record Q3 Revenue",
                "source": "Reuters",
                "url": "https://reuters.com/aapl-q3",
                "published_at": "2026-08-10",
                "relevance_score": 99,  # out of range 1-5 -> validation error
                "impact_direction": "positive",
                "rationale": "Revenue exceeded guidance by 6% on strong services growth.",
            }
        ],
        "summary": "Apple beat expectations.",
        "no_data_found": False,
    }
)

NOT_EVEN_JSON = "Sure! Apple had a great quarter. Revenue was up."


class TestStructuredOutputRetry:
    @patch("app.agent.loop.get_client", return_value=SimpleNamespace())
    @patch("app.agent.loop.create_message_with_retry")
    def test_succeeds_first_try_no_retry(self, mock_create, mock_client):
        mock_create.return_value = _fake_response(VALID_JSON)
        tracer = RequestTracer()

        result, retries, raw = _request_structured_output(
            client=SimpleNamespace(),
            model="claude-sonnet-4-6",
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            ticker="AAPL",
            tracer=tracer,
        )

        assert retries == 0
        assert result.ticker == "AAPL"
        assert len(result.items) == 1
        assert mock_create.call_count == 1

    @patch("app.agent.loop.get_client", return_value=SimpleNamespace())
    @patch("app.agent.loop.create_message_with_retry")
    def test_retries_once_then_succeeds(self, mock_create, mock_client):
        # First call returns invalid schema, second call returns valid.
        mock_create.side_effect = [
            _fake_response(INVALID_JSON_BAD_SCHEMA),
            _fake_response(VALID_JSON),
        ]
        tracer = RequestTracer()

        result, retries, raw = _request_structured_output(
            client=SimpleNamespace(),
            model="claude-sonnet-4-6",
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            ticker="AAPL",
            tracer=tracer,
        )

        assert retries == 1
        assert result.ticker == "AAPL"
        assert mock_create.call_count == 2

        # The retry message should have included the validation error fed
        # back to the model.
        second_call_kwargs = mock_create.call_args_list[1].kwargs
        messages_sent = second_call_kwargs["messages"]
        assert any(
            "validation" in str(m.get("content", "")).lower()
            or "schema" in str(m.get("content", "")).lower()
            for m in messages_sent
        )

    @patch("app.agent.loop.get_client", return_value=SimpleNamespace())
    @patch("app.agent.loop.create_message_with_retry")
    def test_exhausts_retry_and_degrades_gracefully(self, mock_create, mock_client):
        # Both attempts fail validation (not even JSON).
        mock_create.side_effect = [
            _fake_response(NOT_EVEN_JSON),
            _fake_response(NOT_EVEN_JSON),
        ]
        tracer = RequestTracer()

        result, retries, raw = _request_structured_output(
            client=SimpleNamespace(),
            model="claude-sonnet-4-6",
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            ticker="AAPL",
            tracer=tracer,
        )

        # Should not raise -- degraded response returned instead.
        assert retries == 1
        assert result.ticker == "AAPL"
        assert result.items == []
        assert result.no_data_found is True
        assert "could not be parsed" in result.summary.lower()
        assert mock_create.call_count == 2

    @patch("app.agent.loop.get_client", return_value=SimpleNamespace())
    @patch("app.agent.loop.create_message_with_retry")
    def test_handles_markdown_fenced_json(self, mock_create, mock_client):
        fenced = f"```json\n{VALID_JSON}\n```"
        mock_create.return_value = _fake_response(fenced)
        tracer = RequestTracer()

        result, retries, raw = _request_structured_output(
            client=SimpleNamespace(),
            model="claude-sonnet-4-6",
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            ticker="AAPL",
            tracer=tracer,
        )

        assert retries == 0
        assert result.ticker == "AAPL"
