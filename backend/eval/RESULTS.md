# Market Pulse — Evaluation Results

_Generated: 2026-08-17T23:12:50.300363+00:00_

These numbers come from `python -m eval.run_eval`, which runs a hand-labeled golden dataset through the agent under each tool-selection strategy, scores structured precision/recall and an adversarial hallucination check, runs an LLM-as-judge pass, and (with `--ablation`) measures what the grounding/verification layer catches.

## Strategy comparison (agentic vs. router)

| Metric | agentic | router |
| --- | --- | --- |
| Precision | 1 | 1 |
| Recall | 1 | 1 |
| Direction accuracy | 1 | 1 |
| Hallucination rate (adversarial) ↓ | 0 | 0 |
| Schema-validation failure rate ↓ | 0 | 0 |
| Grounding pass rate | 0.750 | 0.500 |
| Avg latency (ms) ↓ | 54569.400 | 49092.400 |
| Avg cost / query (USD) ↓ | 0.313 | 0.232 |

### LLM-as-judge (1–5, higher is better)

| Metric | agentic | router |
| --- | --- | --- |
| Answer quality (1–5) | 3.500 | 3.500 |
| Tool appropriateness (1–5) | 2 | 2.250 |
| Grounding-check functioning (1–5) | 2 | 2.750 |

## Grounding ablation

The grounding pass is a **detection** layer: the agent emits the same summary either way, but without the pass every unsupported claim reaches the user as fact, and with it those claims are flagged as unverified. The detection rate below is the share of factual claims that a no-grounding pipeline would have shipped unverified.

| Metric | agentic | router |
| --- | --- | --- |
| Factual claims checked | 20 | 20 |
| Claims flagged unsupported | 2 | 3 |
| Detection rate (flagged / checked) | 0.100 | 0.150 |
| Cases fully grounded | 3 | 2 |
| Cases | 4 | 4 |

## Golden dataset

The dataset pairs real, dated, independently-verifiable market events with hand-labeled materiality/direction judgments, plus adversarial cases (nonexistent and delisted tickers) that the agent must report as "no data found" rather than fabricating. See `eval/golden_dataset.py`.

---

_Regenerate with `cd backend && python -m eval.run_eval --ablation`. Full JSON in `eval/results/`._
