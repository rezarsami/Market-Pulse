import pytest
from pydantic import ValidationError

from app.models.schemas import NewsAnalysis, NewsItem


def _valid_item(**overrides):
    base = dict(
        headline="Company Beats Q3 Earnings Estimates",
        source="Reuters",
        url="https://reuters.com/article/123",
        published_at="2026-08-15",
        relevance_score=4,
        impact_direction="positive",
        rationale="Revenue beat consensus estimates by 8%, driven by strong cloud segment growth.",
    )
    base.update(overrides)
    return base


class TestNewsItem:
    def test_valid_item_parses(self):
        item = NewsItem(**_valid_item())
        assert item.relevance_score == 4
        assert item.impact_direction == "positive"

    def test_relevance_score_out_of_range_high(self):
        with pytest.raises(ValidationError):
            NewsItem(**_valid_item(relevance_score=6))

    def test_relevance_score_out_of_range_low(self):
        with pytest.raises(ValidationError):
            NewsItem(**_valid_item(relevance_score=0))

    def test_invalid_impact_direction(self):
        with pytest.raises(ValidationError):
            NewsItem(**_valid_item(impact_direction="bullish"))  # not in Literal set

    def test_missing_required_field(self):
        data = _valid_item()
        del data["headline"]
        with pytest.raises(ValidationError):
            NewsItem(**data)

    def test_url_must_start_with_http(self):
        with pytest.raises(ValidationError):
            NewsItem(**_valid_item(url="www.reuters.com/article/123"))

    def test_url_javascript_scheme_rejected(self):
        with pytest.raises(ValidationError):
            NewsItem(**_valid_item(url="javascript:alert(1)"))

    def test_rationale_too_short_rejected(self):
        with pytest.raises(ValidationError):
            NewsItem(**_valid_item(rationale="ok"))

    def test_whitespace_only_headline_rejected(self):
        with pytest.raises(ValidationError):
            NewsItem(**_valid_item(headline="   "))

    def test_headline_gets_trimmed(self):
        item = NewsItem(**_valid_item(headline="  Some Headline  "))
        assert item.headline == "Some Headline"


class TestNewsAnalysis:
    def test_valid_analysis_with_items(self):
        analysis = NewsAnalysis(
            ticker="AAPL",
            items=[NewsItem(**_valid_item())],
            summary="Apple beat estimates on strong iPhone sales.",
            no_data_found=False,
        )
        assert len(analysis.items) == 1
        assert not analysis.no_data_found

    def test_valid_analysis_no_data_found(self):
        analysis = NewsAnalysis(
            ticker="ZZZQXNOPE",
            items=[],
            summary="No material recent news was found for this ticker.",
            no_data_found=True,
        )
        assert analysis.items == []
        assert analysis.no_data_found

    def test_defaults(self):
        analysis = NewsAnalysis(ticker="MSFT", summary="test")
        assert analysis.items == []
        assert analysis.no_data_found is False
