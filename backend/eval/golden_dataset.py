"""
Hand-built golden dataset for evaluation.

Each entry pairs a ticker with a real, dated, well-documented news event
and a ground-truth relevance judgment I've labeled by hand (was this
actually material to the stock's price, yes or no, and roughly what
direction). These are historical facts verifiable via multiple
independent sources (Wikipedia, Reuters, Fed/FDIC records, etc.) as of
this dataset's creation -- not the model's own opinion.

The point of this dataset is NOT to check whether the agent's live web
search happens to surface these exact articles (it may not, since search
results vary over time and by index) -- it's to check two things that
DON'T depend on which specific articles get surfaced:
  1. For queries about a ticker with a known, unambiguous, highly material
     event in the recent past, does the agent's search+judgment pipeline
     find *something* about that event and score it as material
     (relevance_score >= 4) with the correct impact_direction?
  2. For the adversarial case (a nonsense/delisted ticker), does the
     pipeline correctly report "no data found" instead of hallucinating?

This is why each case includes `event_keywords` -- terms that should
appear somewhere in a correctly-grounded item's headline/rationale if the
agent actually found the real event, as opposed to a generic/unrelated
item.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class GoldenCase:
    case_id: str
    ticker: str
    description: str
    # What the agent should ideally surface, for scoring against.
    expected_material: bool  # was there genuinely material news to find?
    expected_impact_direction: Literal["positive", "negative", "neutral", "mixed", "n/a"]
    expected_min_relevance: int  # minimum relevance_score a correctly-grounded item should get
    event_keywords: list[str] = field(default_factory=list)
    # For the adversarial case only:
    is_adversarial: bool = False
    notes: str = ""


GOLDEN_DATASET: list[GoldenCase] = [
    GoldenCase(
        case_id="svb_collapse",
        ticker="SIVB",
        description=(
            "Silicon Valley Bank's collapse and FDIC receivership, March 10, 2023 -- "
            "the second/third-largest bank failure in US history at the time, "
            "triggered by a bank run after a failed capital raise."
        ),
        expected_material=True,
        expected_impact_direction="negative",
        expected_min_relevance=5,
        event_keywords=["silicon valley bank", "svb", "collapse", "fdic", "bank run", "receivership"],
        notes=(
            "SIVB was delisted after FDIC seizure; yfinance may return no live price "
            "data for it today, which is itself a valid 'no data found' case for the "
            "price tool even though news about the historical event may still be "
            "findable via web search."
        ),
    ),
    GoldenCase(
        case_id="apple_iphone_launch_general",
        ticker="AAPL",
        description=(
            "Apple is a large, heavily-covered company that reliably has recent "
            "material news (earnings, product launches, guidance, litigation, or "
            "analyst actions) at any given time."
        ),
        expected_material=True,
        expected_impact_direction="mixed",  # direction varies by what's current; scored leniently
        expected_min_relevance=3,
        event_keywords=["apple", "iphone", "earnings", "guidance", "revenue"],
        notes=(
            "Unlike the SVB case, this is intentionally an open-ended 'is there "
            "*something* material and current' check rather than a single pinned "
            "historical event, since AAPL news is continuous. Used to test that the "
            "agent surfaces genuinely recent items with plausible relevance scores, "
            "not a hallucinated placeholder."
        ),
    ),
    GoldenCase(
        case_id="nonexistent_ticker",
        ticker="ZZZQXNOPE",
        description=(
            "A deliberately nonsensical ticker that does not correspond to any real "
            "listed security."
        ),
        expected_material=False,
        expected_impact_direction="n/a",
        expected_min_relevance=0,
        is_adversarial=True,
        notes=(
            "Adversarial/negative case. The agent must report no_data_found=True "
            "and must NOT fabricate a plausible-sounding company or news items. "
            "This is scored as a pass/fail hallucination check, not a "
            "precision/recall case."
        ),
    ),
    GoldenCase(
        case_id="delisted_ticker",
        ticker="LEHMQQ",
        description=(
            "A delisted/defunct ticker pattern (Lehman-style bankruptcy ticker "
            "suffix) that should not resolve to live price data."
        ),
        expected_material=False,
        expected_impact_direction="n/a",
        expected_min_relevance=0,
        is_adversarial=True,
        notes=(
            "Second adversarial case, specifically targeting the price_history tool: "
            "get_price_history should return no_data_found=True rather than "
            "fabricated OHLC bars."
        ),
    ),
]
