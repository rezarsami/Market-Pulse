"""
Grounding-ablation scoring.

The rest of the harness answers "agentic vs router". This module answers a
sharper, complementary question: **does the grounding/verification pass
catch anything real?**

Framing (and an important honesty note): the grounding pass is a *detection*
layer, not a *generation* layer. The agent produces the same summary whether
or not grounding runs afterwards -- so it would be dishonest to claim
grounding lowers the model's hallucination rate. What grounding changes is
*visibility*: without it, every unsupported claim the model emits reaches the
user presented as fact; with it, those claims are detected and surfaced to the
user (via the GroundingBanner) as "unverified" instead of being silently
trusted.

So the metric this module reports is a **detection rate**: of the distinct
factual claims the model made, what fraction did the verification pass flag as
not traceable to the evidence the agent itself surfaced. That is the number of
claims that WOULD have shipped unverified in a pipeline without a grounding
layer -- which is the honest, defensible value-add to put on a resume.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import GroundingReport, NewsAnalysis


@dataclass
class GroundingAblationRow:
    case_id: str
    ticker: str
    n_items: int
    no_data_found: bool
    checked_claims: int
    flagged_claims: int
    is_fully_grounded: bool
    # Fraction of this case's checked claims the pass flagged as unsupported.
    detection_rate: float


def score_grounding_ablation(
    case_id: str,
    ticker: str,
    analysis: NewsAnalysis,
    grounding: GroundingReport,
) -> GroundingAblationRow:
    checked = grounding.checked_claims
    flagged = len(grounding.flagged_claims)
    rate = round(flagged / checked, 3) if checked else 0.0
    return GroundingAblationRow(
        case_id=case_id,
        ticker=ticker,
        n_items=len(analysis.items),
        no_data_found=analysis.no_data_found,
        checked_claims=checked,
        flagged_claims=flagged,
        is_fully_grounded=grounding.is_fully_grounded,
        detection_rate=rate,
    )


@dataclass
class GroundingAblationSummary:
    strategy: str
    n_cases_with_claims: int
    total_checked_claims: int
    total_flagged_claims: int
    # Headline number: across all checked claims, the fraction flagged as
    # unsupported. This is the share of factual claims that a no-grounding
    # pipeline would have shipped to the user unverified.
    aggregate_detection_rate: float
    cases_fully_grounded: int
    n_cases: int


def aggregate_grounding_ablation(
    rows: list[GroundingAblationRow], strategy: str
) -> GroundingAblationSummary:
    with_claims = [r for r in rows if r.checked_claims > 0]
    total_checked = sum(r.checked_claims for r in with_claims)
    total_flagged = sum(r.flagged_claims for r in with_claims)
    rate = round(total_flagged / total_checked, 3) if total_checked else 0.0
    return GroundingAblationSummary(
        strategy=strategy,
        n_cases_with_claims=len(with_claims),
        total_checked_claims=total_checked,
        total_flagged_claims=total_flagged,
        aggregate_detection_rate=rate,
        cases_fully_grounded=sum(1 for r in rows if r.is_fully_grounded),
        n_cases=len(rows),
    )
