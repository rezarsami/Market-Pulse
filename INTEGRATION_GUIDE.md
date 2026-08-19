# Grounding-ablation feature — drop-in guide

## What this adds

Your eval harness already compared **agentic vs. router** and did precision/recall,
an adversarial hallucination check, and an LLM-as-judge pass. This feature adds the
one thing that was missing for an AI/ML resume: a **grounding ablation** that measures
what the verification layer actually catches, plus a committed, human-readable
`RESULTS.md` so a reviewer sees real numbers without running anything.

Importantly, it reuses the grounding call the harness already makes — so it adds
**no extra API cost** per run.

## Files

| File | Action |
| --- | --- |
| `backend/eval/ablation.py` | **new** — detection-rate scoring for the grounding pass |
| `backend/eval/report_md.py` | **new** — renders the report dict to `RESULTS.md` |
| `backend/eval/run_eval.py` | **replace** — wires in the ablation + `--ablation` flag |

Copy the two new files into `backend/eval/` and overwrite `run_eval.py` with the
version here.

## Run it

```bash
cd backend
python -m eval.run_eval --ablation
```

This runs the full golden dataset under both strategies, prints the comparison
table (now with a grounding-ablation block), writes JSON to `eval/results/`, and
writes `backend/eval/RESULTS.md`. Commit `RESULTS.md` so it renders on GitHub.

To iterate cheaply while testing, run one case:

```bash
python -m eval.run_eval --ablation --cases svb_collapse --strategy router
```

## An honesty note (this matters in interviews)

The ablation reports a **detection rate**, not a reduction in the model's
hallucination rate. The agent emits the same summary whether or not grounding runs;
grounding changes *visibility* — unsupported claims get flagged as unverified instead
of shipping as fact. Framing it as "grounding lowers hallucinations" would be wrong
and an interviewer would catch it. The detection-rate framing is defensible: it's the
share of factual claims a no-grounding pipeline would have shipped unverified.

---

## Suggested README section (resume-facing)

Paste near the top of your main `README.md`, after the one-line description. Replace
the bracketed numbers once you've run it for real.

```markdown
## Evaluation

Market Pulse is evaluated with a hand-labeled golden dataset and a reproducible
harness (`backend/eval/`) rather than vibes. Every push, the same suite measures:

- **Structured precision / recall** against labeled materiality + direction.
- **Adversarial hallucination rate** — nonexistent and delisted tickers that the
  agent must report as "no data found" instead of fabricating.
- **Tool-selection ablation** — the same cases run under an autonomous *agentic*
  loop and a cheap *router* pre-classifier, compared on quality, latency, and
  cost/query.
- **Grounding ablation** — a detection-rate measurement of the citation-
  verification pass: the share of factual claims that a pipeline without the
  grounding layer would have shipped to the user unverified.

See [`backend/eval/RESULTS.md`](backend/eval/RESULTS.md) for current numbers.

Headline finding: the router strategy cut cost/query by ~[X]% and latency by
~[Y]% versus the agentic loop at comparable answer quality, and the grounding
pass flagged [Z]% of factual claims as unsupported — claims that would otherwise
reach the user as fact.
```

## One-line resume bullet

> Built a citation-grounded market-intelligence agent (Claude + native web search,
> hand-rolled tool loop) with a reproducible eval harness measuring precision/recall,
> adversarial hallucination rate, and a router-vs-agentic cost/latency ablation;
> router cut cost/query ~[X]% at comparable quality.
