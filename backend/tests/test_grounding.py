"""
Tests for the grounding verification pass (app.agent.grounding).

We mock the Anthropic API call so no real network/API access is needed.
The key test confirms that when the (mocked) verifier model reports an
unsupported claim, run_grounding_check surfaces it as a flagged claim
rather than silently returning is_fully_grounded=True.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.agent.grounding import run_grounding_check
from app.models.schemas import NewsAnalysis, NewsItem
from app.observability.tracing import RequestTracer


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _fake_response(text: str):
    return SimpleNamespace(
        content=[_text_block(text)],
        usage=SimpleNamespace(input_tokens=200, output_tokens=80),
    )


def _analysis_with_unsupported_claim() -> NewsAnalysis:
    item = NewsItem(
        headline="Company Reports Q3 Revenue Growth",
        source="Reuters",
        url="https://reuters.com/article/1",
        published_at="2026-08-10",
        relevance_score=4,
        impact_direction="positive",
        rationale="Revenue grew 5% year over year on stronger cloud demand.",
    )
    # The summary asserts a specific fact (a CEO resignation) that is NOT
    # present anywhere in the evidence item above -- this is the
    # unsupported claim the grounding pass should catch.
    return NewsAnalysis(
        ticker="TEST",
        items=[item],
        summary=(
            "The company reported 5% revenue growth. Additionally, the CEO "
            "abruptly resigned amid an accounting scandal, spooking investors."
        ),
        no_data_found=False,
    )


class TestGroundingCheck:
    @patch("app.agent.grounding.get_client", return_value=SimpleNamespace())
    @patch("app.agent.grounding.create_message_with_retry")
    def test_flags_unsupported_claim(self, mock_create, mock_client):
        verifier_output = json.dumps(
            {
                "is_fully_grounded": False,
                "checked_claims": 2,
                "flagged_claims": [
                    {
                        "claim": "CEO abruptly resigned amid an accounting scandal",
                        "reason": "No evidence item mentions a CEO resignation or accounting scandal.",
                    }
                ],
            }
        )
        mock_create.return_value = _fake_response(verifier_output)

        tracer = RequestTracer()
        report = run_grounding_check(_analysis_with_unsupported_claim(), tracer)

        assert report.is_fully_grounded is False
        assert len(report.flagged_claims) == 1
        assert "resign" in report.flagged_claims[0].claim.lower()

    @patch("app.agent.grounding.get_client", return_value=SimpleNamespace())
    @patch("app.agent.grounding.create_message_with_retry")
    def test_fully_grounded_summary_passes(self, mock_create, mock_client):
        verifier_output = json.dumps(
            {"is_fully_grounded": True, "checked_claims": 1, "flagged_claims": []}
        )
        mock_create.return_value = _fake_response(verifier_output)

        item = NewsItem(
            headline="Company Reports Q3 Revenue Growth",
            source="Reuters",
            url="https://reuters.com/article/1",
            published_at="2026-08-10",
            relevance_score=4,
            impact_direction="positive",
            rationale="Revenue grew 5% year over year on stronger cloud demand.",
        )
        analysis = NewsAnalysis(
            ticker="TEST",
            items=[item],
            summary="The company reported 5% revenue growth on stronger cloud demand.",
            no_data_found=False,
        )

        tracer = RequestTracer()
        report = run_grounding_check(analysis, tracer)

        assert report.is_fully_grounded is True
        assert report.flagged_claims == []

    def test_no_data_found_case_skips_check_and_is_trivially_grounded(self):
        # When the agent found nothing, there's nothing to fact-check --
        # this should NOT make a real API call at all.
        analysis = NewsAnalysis(
            ticker="ZZZQXNOPE", items=[], summary="No data found.", no_data_found=True
        )
        tracer = RequestTracer()

        with patch("app.agent.grounding.get_client") as mock_get_client:
            report = run_grounding_check(analysis, tracer)
            mock_get_client.assert_not_called()

        assert report.is_fully_grounded is True
        assert report.checked_claims == 0

    @patch("app.agent.grounding.get_client", return_value=SimpleNamespace())
    @patch("app.agent.grounding.create_message_with_retry")
    def test_verifier_call_failure_fails_safe_not_grounded(self, mock_create, mock_client):
        mock_create.side_effect = RuntimeError("API unavailable")

        item = NewsItem(
            headline="Company Reports Q3 Revenue Growth",
            source="Reuters",
            url="https://reuters.com/article/1",
            published_at="2026-08-10",
            relevance_score=4,
            impact_direction="positive",
            rationale="Revenue grew 5% year over year.",
        )
        analysis = NewsAnalysis(
            ticker="TEST", items=[item], summary="Revenue grew 5%.", no_data_found=False
        )

        tracer = RequestTracer()
        report = run_grounding_check(analysis, tracer)

        # Must fail SAFE: if we can't verify, we don't claim grounded.
        assert report.is_fully_grounded is False
        assert len(report.flagged_claims) == 1

    @patch("app.agent.grounding.get_client", return_value=SimpleNamespace())
    @patch("app.agent.grounding.create_message_with_retry")
    def test_malformed_verifier_output_fails_safe(self, mock_create, mock_client):
        mock_create.return_value = _fake_response("not valid json at all")

        item = NewsItem(
            headline="Company Reports Q3 Revenue Growth",
            source="Reuters",
            url="https://reuters.com/article/1",
            published_at="2026-08-10",
            relevance_score=4,
            impact_direction="positive",
            rationale="Revenue grew 5% year over year.",
        )
        analysis = NewsAnalysis(
            ticker="TEST", items=[item], summary="Revenue grew 5%.", no_data_found=False
        )

        tracer = RequestTracer()
        report = run_grounding_check(analysis, tracer)

        assert report.is_fully_grounded is False
