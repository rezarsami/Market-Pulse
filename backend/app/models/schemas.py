"""
Pydantic schemas for structured, validated agent output.

The core value-add of this project is turning "the model said some stuff
about news" into a validated, typed structure the frontend (and any
downstream consumer) can trust. Validation failures are a first-class
metric, not just something we quietly retry.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class NewsItem(BaseModel):
    """A single piece of news, judged for relevance to a ticker's price."""

    headline: str = Field(..., min_length=1, max_length=300)
    source: str = Field(..., min_length=1, max_length=120)
    url: str = Field(..., min_length=1, max_length=2000)
    published_at: str = Field(
        ..., description="Best-effort date/time string as reported by the source"
    )
    relevance_score: int = Field(..., ge=1, le=5)
    impact_direction: Literal["positive", "negative", "neutral", "mixed"]
    rationale: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="1-2 sentences, must reference something specific in the article",
    )

    @field_validator("url")
    @classmethod
    def url_looks_like_url(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v

    @field_validator("headline", "source", "rationale")
    @classmethod
    def not_just_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty/whitespace")
        return v.strip()


class NewsAnalysis(BaseModel):
    """The full structured output the agent must produce for a ticker."""

    ticker: str
    items: list[NewsItem] = Field(default_factory=list)
    summary: str = Field(
        ..., description="Synthesized narrative summary across all news items"
    )
    no_data_found: bool = Field(
        default=False,
        description="True if the agent found no material news; summary should say so plainly",
    )


class GroundingFlag(BaseModel):
    """A single claim from the summary that failed the grounding check."""

    claim: str
    reason: str


class GroundingReport(BaseModel):
    is_fully_grounded: bool
    checked_claims: int
    flagged_claims: list[GroundingFlag] = Field(default_factory=list)


class ToolCallLog(BaseModel):
    tool_name: str
    input: dict
    latency_ms: float
    output_summary: str


class CostBreakdown(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    web_searches: int = 0
    estimated_cost_usd: float = 0.0


class AnalyzeResponse(BaseModel):
    ticker: str
    question: Optional[str] = None
    strategy_used: Literal["agentic", "router"]
    news_analysis: NewsAnalysis
    grounding_report: GroundingReport
    schema_validation_retries: int = 0
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    cost_breakdown: list[CostBreakdown] = Field(default_factory=list)
    total_estimated_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    request_id: str


class PriceBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistoryResponse(BaseModel):
    ticker: str
    period: str
    interval: str
    bars: list[PriceBar]
    currency: Optional[str] = None
    no_data_found: bool = False


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    question: Optional[str] = Field(default=None, max_length=500)
    strategy_override: Optional[Literal["agentic", "router"]] = None

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase_alnum(cls, v: str) -> str:
        v = v.strip().upper()
        return v
