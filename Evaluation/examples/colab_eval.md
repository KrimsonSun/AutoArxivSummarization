# Colab quickstart — full pipeline + evaluation

Runs RefinedSummarization (3-LLM debate) + Evaluation (coverage / hallucination)
end-to-end, on one paper, in 6 cells. No GPU needed (everything goes through
OpenRouter via API).

## Cell 1 — clone + install BOTH modules

```python
!git clone <your-fork-url> AutoArxiv     # or upload a zip and unzip
%cd AutoArxiv

!pip install -e ./RefinedSummarization[dev] -q
!pip install -e ./Evaluation[dev] -q
```

## Cell 2 — credentials (one OpenRouter key powers both)

```python
import os
os.environ["OPENAI_API_KEY"]  = "sk-or-v1-XXXXXXXX"   # paste your OpenRouter key
os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["DEV_MODE"]        = "0"
```

## Cell 3 — fetch a paper

```python
!curl -sSL https://arxiv.org/pdf/1706.03762 -o /tmp/paper.pdf
```

## Cell 4 — run the summarization pipeline

```python
%cd RefinedSummarization
!python -m src.cli \
    --pdf /tmp/paper.pdf \
    --output-format json \
    --save
# saved to outputs/json/<arxiv_id>.json + outputs/markdown/<arxiv_id>.md
%cd ..
```

## Cell 5 — run the evaluator

```python
%cd Evaluation
!python -m src.cli \
    --summary ../RefinedSummarization/outputs/json/1706.03762.json \
    --paper   /tmp/paper.pdf \
    --output  outputs/1706.03762.eval.json
```

## Cell 6 — view the metrics

```python
import json
report = json.load(open("outputs/1706.03762.eval.json"))
print(f"Evidence Coverage:   {report['evidence_coverage']:.3f}")
print(f"Hallucination Rate:  {report['hallucination_rate']:.3f}")
print(f"Total Claims:        {report['total_claims']}")
print(f"Counts:              {report['counts']}")

# Spot-check the first few per-claim verdicts
for v in report["per_claim"][:5]:
    print(f"\n[{v['claim_id']}] verdict={v['verdict']}")
    print(f"  evidence: {v['evidence_paragraphs']}")
    print(f"  rationale: {v['rationale'][:120]}")
```

## Comparing against a baseline

To prove "RefinedSummarization beats baseline X on coverage and hallucination",
you need one extra summary — generate it with whatever your baseline is
(e.g. a single-LLM zero-shot summary), save it as `baseline.md`, then:

```python
!python -m src.cli \
    --summary baseline.md \
    --paper   /tmp/paper.pdf \
    --output  outputs/1706.03762.baseline.eval.json
```

Now you have two reports for the same paper. Compute deltas across N papers:

```python
import json, glob, statistics
def load(path): return json.load(open(path))

ours      = [load(p) for p in sorted(glob.glob("outputs/*.eval.json"))      if "baseline" not in p]
baseline  = [load(p) for p in sorted(glob.glob("outputs/*.baseline.eval.json"))]

def mean(field, reports):
    return statistics.mean(r[field] for r in reports)

print("Coverage:       ours=%.3f  baseline=%.3f  Δ=%+.3f"
      % (mean("evidence_coverage", ours), mean("evidence_coverage", baseline),
         mean("evidence_coverage", ours) - mean("evidence_coverage", baseline)))
print("Hallucination:  ours=%.3f  baseline=%.3f  Δ=%+.3f"
      % (mean("hallucination_rate", ours), mean("hallucination_rate", baseline),
         mean("hallucination_rate", ours) - mean("hallucination_rate", baseline)))
```

## Cost guardrail

| Step                            | Cost per paper (Llama 3.3 70B) |
|---------------------------------|--------------------------------|
| RefinedSummarization pipeline   | ~$0.05–0.15                    |
| Evaluation (1 summary)          | ~$0.02–0.06                    |
| **Total per paper, both modules** | **~$0.07–0.21**              |

For a 30-paper experiment running both pipelines on each paper (~ours +
baseline = 60 evaluations): expect **$5–15 total**. Set OpenRouter spending
caps at https://openrouter.ai/settings/credits.
