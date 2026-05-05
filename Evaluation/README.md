# Evaluation — Coverage + Hallucination Scorer

Independent companion to `RefinedSummarization/`. Takes a generated summary
+ the original paper, runs the 4-step claim verification pipeline, and
emits two paper-grade metrics:

- **Evidence Coverage** = fraction of summary claims supported by the paper.
- **Hallucination Rate** = fraction of claims unsupported or contradicted.

```
summary.json + paper.pdf
        ↓
Step 1: LLM claim extraction       → list[Claim] (atomic, traceable)
        ↓
Step 2: BM25 retrieval per claim   → top-k paper paragraphs (no LLM)
        ↓
Step 3: LLM NLI verdict per claim  → Supported / Partial / Unsupported / Contradicted
        ↓
Step 4: Aggregate                  → coverage + hallucination_rate
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
$EDITOR .env   # set OPENAI_API_KEY (your OpenRouter key)
```

## Usage

```bash
# 1. Run RefinedSummarization to produce a FinalSummary JSON:
#      cd ../RefinedSummarization
#      python -m src.cli --pdf paper.pdf --save
# 2. Score it:
python -m src.cli \
    --summary  ../RefinedSummarization/outputs/json/<id>.json \
    --paper    ../RefinedSummarization/tests/fixtures/<id>.pdf \
    --output   outputs/<id>.eval.json
```

The same evaluator works against ANY summary (not just RefinedSummarization
output) — pass a `.md` or `.txt` file via `--summary` to score a baseline.

## Configuration

`config/default.yaml` controls:

- Which LLM does claim extraction (Step 1) — defaults to Llama 3.3 70B
- Which LLM does NLI verification (Step 3) — defaults to Llama 3.3 70B
- Retrieval method — `bm25` (default, no GPU) or `embedding`
  (requires `pip install -e ".[embedding]"`)
- Top-k for retrieval (default 5)
- Scoring tweaks: partial-credit weight, treat-unsupported-as-hallucination

Both LLM models can be swapped via OpenRouter just by editing the YAML —
no code change.

## Output schema

```json
{
  "arxiv_id": "1706.03762",
  "title": "Attention Is All You Need",
  "paper_paragraph_count": 85,
  "total_claims": 27,
  "counts": {"supported": 19, "partial": 4, "unsupported": 3, "contradicted": 1},
  "evidence_coverage": 0.778,
  "hallucination_rate": 0.148,
  "per_claim": [
    {"claim_id": "C1", "verdict": "Supported", "evidence_paragraphs": ["P3"], "rationale": "..."},
    ...
  ],
  "eval_config": { ... },
  "timestamp": "..."
}
```

## Cost (OpenRouter, Llama 3.3 70B)

Per (summary × paper) evaluation:
- 1 claim-extraction call (~5k input, ~2k output)
- N verification calls (~3k input, ~0.3k output each), N ≈ 20–40 claims

Total ≈ **$0.02–0.06 per evaluation**.

## Colab quickstart

See [`examples/colab_eval.md`](examples/colab_eval.md).

## Tests

```bash
pytest tests/ -q     # 16 unit + mocked-E2E, no API needed
```
