"""
Render an eval report dict into a Markdown file committed to the repo.

The JSON reports in eval/results/ are the source of truth; this produces the
human-readable RESULTS.md that the top-level README links to, so a reader
(recruiter, reviewer) sees real numbers without running anything.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone


def _fmt(v) -> str:
    if isinstance(v, float):
        # Whole-number floats (latency, counts) render without decimals;
        # fractional rates keep 3 places.
        if v.is_integer():
            return str(int(v))
        return f"{v:.3f}"
    return str(v)


def render_markdown(report: dict) -> str:
    strategies = list(report.get("strategies", {}).keys())
    generated = report.get("generated_at", datetime.now(timezone.utc).isoformat())

    lines: list[str] = []
    lines.append("# Market Pulse — Evaluation Results")
    lines.append("")
    lines.append(f"_Generated: {generated}_")
    lines.append("")
    lines.append(
        "These numbers come from `python -m eval.run_eval`, which runs a "
        "hand-labeled golden dataset through the agent under each tool-selection "
        "strategy, scores structured precision/recall and an adversarial "
        "hallucination check, runs an LLM-as-judge pass, and (with `--ablation`) "
        "measures what the grounding/verification layer catches."
    )
    lines.append("")

    # --- Strategy comparison table ---
    lines.append("## Strategy comparison (agentic vs. router)")
    lines.append("")
    metric_rows = [
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("direction_accuracy", "Direction accuracy"),
        ("hallucination_rate", "Hallucination rate (adversarial) ↓"),
        ("schema_validation_failure_rate", "Schema-validation failure rate ↓"),
        ("avg_grounding_pass_rate", "Grounding pass rate"),
        ("avg_latency_ms", "Avg latency (ms) ↓"),
        ("avg_cost_usd", "Avg cost / query (USD) ↓"),
    ]
    header = "| Metric | " + " | ".join(strategies) + " |"
    sep = "| --- | " + " | ".join("---" for _ in strategies) + " |"
    lines.append(header)
    lines.append(sep)
    for key, label in metric_rows:
        vals = [
            _fmt(report["strategies"][s]["metrics"].get(key, "—")) for s in strategies
        ]
        lines.append(f"| {label} | " + " | ".join(vals) + " |")
    lines.append("")

    # LLM-judge sub-table
    judge_rows = [
        ("avg_answer_quality", "Answer quality (1–5)"),
        ("avg_tool_appropriateness", "Tool appropriateness (1–5)"),
        ("avg_grounding_check_functioning", "Grounding-check functioning (1–5)"),
    ]
    lines.append("### LLM-as-judge (1–5, higher is better)")
    lines.append("")
    lines.append(header)
    lines.append(sep)
    for key, label in judge_rows:
        vals = [
            _fmt(report["strategies"][s]["llm_judge"].get(key, "—")) for s in strategies
        ]
        lines.append(f"| {label} | " + " | ".join(vals) + " |")
    lines.append("")

    # --- Grounding ablation, if present ---
    if any("grounding_ablation" in report["strategies"][s] for s in strategies):
        lines.append("## Grounding ablation")
        lines.append("")
        lines.append(
            "The grounding pass is a **detection** layer: the agent emits the same "
            "summary either way, but without the pass every unsupported claim reaches "
            "the user as fact, and with it those claims are flagged as unverified. "
            "The detection rate below is the share of factual claims that a "
            "no-grounding pipeline would have shipped unverified."
        )
        lines.append("")
        ab_rows = [
            ("total_checked_claims", "Factual claims checked"),
            ("total_flagged_claims", "Claims flagged unsupported"),
            ("aggregate_detection_rate", "Detection rate (flagged / checked)"),
            ("cases_fully_grounded", "Cases fully grounded"),
            ("n_cases", "Cases"),
        ]
        lines.append(header)
        lines.append(sep)
        for key, label in ab_rows:
            vals = []
            for s in strategies:
                ab = report["strategies"][s].get("grounding_ablation", {})
                vals.append(_fmt(ab.get(key, "—")))
            lines.append(f"| {label} | " + " | ".join(vals) + " |")
        lines.append("")

    lines.append("## Golden dataset")
    lines.append("")
    lines.append(
        "The dataset pairs real, dated, independently-verifiable market events with "
        "hand-labeled materiality/direction judgments, plus adversarial cases "
        "(nonexistent and delisted tickers) that the agent must report as "
        "\"no data found\" rather than fabricating. See `eval/golden_dataset.py`."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "_Regenerate with `cd backend && python -m eval.run_eval --ablation`. "
        "Full JSON in `eval/results/`._"
    )
    lines.append("")
    return "\n".join(lines)


def write_markdown(report: dict, out_path: str) -> None:
    md = render_markdown(report)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(md)
