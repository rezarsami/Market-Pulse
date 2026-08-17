"""
Main evaluation harness entry point.

Runs the golden dataset through BOTH tool-selection strategies (agentic
and router), computes precision/recall/hallucination metrics for each,
runs the LLM-as-judge pass, and writes a report to eval/results/.

Usage:
    cd backend
    python -m eval.run_eval
    python -m eval.run_eval --strategy router   # run only one strategy
    python -m eval.run_eval --cases svb_collapse,nonexistent_ticker
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.grounding import run_grounding_check
from app.agent.loop import run_agent
from app.observability.tracing import RequestTracer
from eval.golden_dataset import GOLDEN_DATASET, GoldenCase
from eval.llm_judge import judge_case
from eval.metrics import CaseScore, aggregate, score_case

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def run_single_case(case: GoldenCase, strategy: str) -> dict:
    tracer = RequestTracer()
    start = time.time()
    try:
        result = run_agent(
            ticker=case.ticker, question=None, tracer=tracer, strategy=strategy
        )
    except Exception as e:
        print(f"  [{case.case_id}/{strategy}] FAILED: {e}")
        return {
            "case_id": case.case_id,
            "strategy": strategy,
            "error": str(e),
        }
    latency_ms = round((time.time() - start) * 1000, 2)

    grounding = run_grounding_check(result.news_analysis, tracer)
    case_score = score_case(case, result.news_analysis)
    tool_names = [tc["tool_name"] for tc in tracer.tool_calls]
    judge_score = judge_case(case, result.news_analysis, grounding, tool_names)

    print(
        f"  [{case.case_id}/{strategy}] items={len(result.news_analysis.items)} "
        f"no_data_found={result.news_analysis.no_data_found} "
        f"schema_retries={result.schema_validation_retries} "
        f"grounded={grounding.is_fully_grounded} "
        f"cost=${tracer.total_cost_usd:.4f} latency={latency_ms}ms"
    )

    return {
        "case_id": case.case_id,
        "strategy": strategy,
        "ticker": case.ticker,
        "news_analysis": result.news_analysis.model_dump(),
        "grounding_report": grounding.model_dump(),
        "schema_validation_retries": result.schema_validation_retries,
        "tool_calls": tracer.tool_calls,
        "tool_names_called": tool_names,
        "total_cost_usd": tracer.total_cost_usd,
        "latency_ms": latency_ms,
        "case_score": asdict(case_score),
        "judge_score": asdict(judge_score),
        "search_mode": result.search_mode,
    }


def run_harness(strategies: list[str], cases: list[GoldenCase]) -> dict:
    all_runs: dict[str, list[dict]] = {s: [] for s in strategies}

    for strategy in strategies:
        print(f"\n=== Running strategy: {strategy} ===")
        for case in cases:
            run = run_single_case(case, strategy)
            all_runs[strategy].append(run)

    report: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "strategies": {}}

    for strategy in strategies:
        runs = all_runs[strategy]
        valid_runs = [r for r in runs if "error" not in r]

        case_scores = [CaseScore(**r["case_score"]) for r in valid_runs]
        schema_retries = [r["schema_validation_retries"] for r in valid_runs]
        grounding_passes = [r["grounding_report"]["is_fully_grounded"] for r in valid_runs]
        latencies = [r["latency_ms"] for r in valid_runs]
        costs = [r["total_cost_usd"] for r in valid_runs]

        metrics = aggregate(
            case_scores, strategy, schema_retries, grounding_passes, latencies, costs
        )

        judge_scores = [r["judge_score"] for r in valid_runs]
        avg_answer_quality = (
            sum(j["answer_quality"] for j in judge_scores) / len(judge_scores)
            if judge_scores
            else 0
        )
        avg_tool_appropriateness = (
            sum(j["tool_appropriateness"] for j in judge_scores) / len(judge_scores)
            if judge_scores
            else 0
        )
        avg_grounding_functioning = (
            sum(j["grounding_check_functioning"] for j in judge_scores) / len(judge_scores)
            if judge_scores
            else 0
        )

        report["strategies"][strategy] = {
            "metrics": asdict(metrics),
            "llm_judge": {
                "avg_answer_quality": round(avg_answer_quality, 2),
                "avg_tool_appropriateness": round(avg_tool_appropriateness, 2),
                "avg_grounding_check_functioning": round(avg_grounding_functioning, 2),
            },
            "n_errors": len(runs) - len(valid_runs),
            "runs": runs,
        }

    return report


def print_comparison_table(report: dict) -> None:
    strategies = list(report["strategies"].keys())
    if len(strategies) < 1:
        return

    print("\n" + "=" * 78)
    print("STRATEGY COMPARISON")
    print("=" * 78)
    headers = ["metric"] + strategies
    rows = [
        "precision",
        "recall",
        "direction_accuracy",
        "hallucination_rate",
        "schema_validation_failure_rate",
        "avg_grounding_pass_rate",
        "avg_latency_ms",
        "avg_cost_usd",
    ]
    col_width = 34
    print(f"{'metric':<{col_width}}" + "".join(f"{s:<20}" for s in strategies))
    for row in rows:
        vals = [str(report["strategies"][s]["metrics"][row]) for s in strategies]
        print(f"{row:<{col_width}}" + "".join(f"{v:<20}" for v in vals))
    print()
    judge_rows = ["avg_answer_quality", "avg_tool_appropriateness", "avg_grounding_check_functioning"]
    for row in judge_rows:
        vals = [str(report["strategies"][s]["llm_judge"][row]) for s in strategies]
        print(f"{row:<{col_width}}" + "".join(f"{v:<20}" for v in vals))
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(description="Run the Market Pulse evaluation harness")
    parser.add_argument(
        "--strategy",
        choices=["agentic", "router", "both"],
        default="both",
        help="Which strategy/strategies to run",
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="Comma-separated case_ids to run (default: full golden dataset)",
    )
    args = parser.parse_args()

    strategies = ["agentic", "router"] if args.strategy == "both" else [args.strategy]

    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in GOLDEN_DATASET if c.case_id in wanted]
    else:
        cases = GOLDEN_DATASET

    print(f"Running eval harness: strategies={strategies}, cases={[c.case_id for c in cases]}")

    report = run_harness(strategies, cases)
    print_comparison_table(report)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(
        RESULTS_DIR, f"eval_report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report written to {out_path}")

    # Also write/overwrite a "latest" pointer for the README to reference.
    latest_path = os.path.join(RESULTS_DIR, "latest.json")
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=2, default=str)


if __name__ == "__main__":
    main()
