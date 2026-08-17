"""
Scoring functions: precision/recall against golden-dataset ground truth,
plus the hallucination/adversarial check. These are actual numeric
computations over structured fields (relevance_score, impact_direction,
no_data_found) -- not an LLM's opinion of quality.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import NewsAnalysis
from eval.golden_dataset import GoldenCase


@dataclass
class CaseScore:
    case_id: str
    ticker: str
    is_adversarial: bool
    # For non-adversarial cases:
    found_material_item: bool = False
    correct_direction: bool = False
    matched_keyword: bool = False
    max_relevance_found: int = 0
    # For adversarial cases:
    correctly_reported_no_data: bool = False
    hallucinated: bool = False
    notes: str = ""


def score_case(case: GoldenCase, analysis: NewsAnalysis) -> CaseScore:
    score = CaseScore(case_id=case.case_id, ticker=case.ticker, is_adversarial=case.is_adversarial)

    if case.is_adversarial:
        # Pass criteria: agent reports no_data_found and produced no items
        # that look like fabricated specifics (no items at all is the
        # clean pass; any item is treated as a potential hallucination
        # since there is no real company here).
        score.correctly_reported_no_data = analysis.no_data_found and len(analysis.items) == 0
        score.hallucinated = len(analysis.items) > 0 or not analysis.no_data_found
        score.notes = case.notes
        return score

    if not analysis.items:
        score.notes = "agent surfaced no items"
        return score

    score.max_relevance_found = max((i.relevance_score for i in analysis.items), default=0)

    for item in analysis.items:
        text_blob = f"{item.headline} {item.rationale}".lower()
        kw_hit = any(kw.lower() in text_blob for kw in case.event_keywords)
        if kw_hit:
            score.matched_keyword = True
            if item.relevance_score >= case.expected_min_relevance:
                score.found_material_item = True
            if case.expected_impact_direction == "mixed":
                score.correct_direction = True  # lenient: any direction acceptable
            elif item.impact_direction == case.expected_impact_direction:
                score.correct_direction = True

    return score


@dataclass
class AggregateMetrics:
    strategy: str
    n_cases: int
    n_non_adversarial: int
    n_adversarial: int
    precision: float  # of items surfaced, how many were relevant/correct
    recall: float  # of expected material events, how many did we find
    direction_accuracy: float
    hallucination_rate: float  # fraction of adversarial cases that hallucinated
    schema_validation_failure_rate: float
    avg_grounding_pass_rate: float
    avg_latency_ms: float
    avg_cost_usd: float


def aggregate(
    scores: list[CaseScore],
    strategy: str,
    schema_retries: list[int],
    grounding_passes: list[bool],
    latencies_ms: list[float],
    costs_usd: list[float],
) -> AggregateMetrics:
    non_adv = [s for s in scores if not s.is_adversarial]
    adv = [s for s in scores if s.is_adversarial]

    # Precision: of non-adversarial cases where the agent found *a*
    # keyword-matching item, how many scored it at/above expected
    # relevance (i.e. didn't under- or mis-judge it).
    matched = [s for s in non_adv if s.matched_keyword]
    precision = (
        sum(1 for s in matched if s.found_material_item) / len(matched) if matched else 0.0
    )

    # Recall: of all non-adversarial cases expected to have material news,
    # how many did the agent surface *something* keyword-matching for.
    expected_material_cases = [s for s in non_adv]  # all non-adv cases in this dataset expect material news
    recall = (
        sum(1 for s in expected_material_cases if s.matched_keyword) / len(expected_material_cases)
        if expected_material_cases
        else 0.0
    )

    direction_accuracy = (
        sum(1 for s in non_adv if s.correct_direction) / len(non_adv) if non_adv else 0.0
    )

    hallucination_rate = (
        sum(1 for s in adv if s.hallucinated) / len(adv) if adv else 0.0
    )

    schema_failure_rate = (
        sum(1 for r in schema_retries if r > 0) / len(schema_retries) if schema_retries else 0.0
    )

    grounding_pass_rate = (
        sum(1 for g in grounding_passes if g) / len(grounding_passes) if grounding_passes else 0.0
    )

    avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
    avg_cost = sum(costs_usd) / len(costs_usd) if costs_usd else 0.0

    return AggregateMetrics(
        strategy=strategy,
        n_cases=len(scores),
        n_non_adversarial=len(non_adv),
        n_adversarial=len(adv),
        precision=round(precision, 3),
        recall=round(recall, 3),
        direction_accuracy=round(direction_accuracy, 3),
        hallucination_rate=round(hallucination_rate, 3),
        schema_validation_failure_rate=round(schema_failure_rate, 3),
        avg_grounding_pass_rate=round(grounding_pass_rate, 3),
        avg_latency_ms=round(avg_latency, 1),
        avg_cost_usd=round(avg_cost, 6),
    )
