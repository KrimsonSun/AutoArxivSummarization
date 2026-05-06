# Refine-OneVision-Summary

A second-generation summarization pipeline that tests a different
hypothesis from the original `RefinedSummarization` module:

> **Hypothesis (under test).** The bottleneck of the v1/v2 multi-agent
> pipeline is the *refiner* step. By the time three drafts arrive, the
> refiner is asked to do a hard task — merge them into a faithful
> single output without losing any specific fact — and it tends to
> intersect rather than union. Skip the merge entirely: pick **one
> winning draft** via multi-agent selection (a consensus task that
> debate is empirically good at), then *augment* that single draft
> with missing facts retrieved from the paper.

## Pipeline (5 stages)

```
Stage 1   3 LLMs (Llama-3.3-70B, Qwen-2.5-72B, DeepSeek-V3) each
          produce one independent draft, ≤ 1000 words.

Stage 2   GAME-THEORY SELECTION (3 rounds)
          Round 1: each LLM ranks all 3 drafts (anonymous labels).
          Round 2: each LLM sees the other two rankings + reasoning,
                   may revise its own.
          Round 3: same; allows convergence.
          Aggregate: Borda count → ONE winning draft.

Stage 3   VERIFIER on (winning draft, FULL paper paragraphs)
          Note: this is the key fix vs the v1 pipeline. v1's verifier
          only saw paragraph short-summaries (lossy). Here the verifier
          reads the full paragraph text.
          Output: missing_info / distorted / unsupported issues.

Stage 4   RETRIEVER picks paper paragraphs that resolve each issue.

Stage 5   REFINER takes (winning draft, issues, evidence) and produces
          the final summary, ≤ 1000 words. NO merge — just
          insertion / correction of the missing or distorted facts.
```

## What is intentionally different from `RefinedSummarization`

| Choice | v1/v2 (`RefinedSummarization`) | This module (`Refine-OneVision-Summary`) |
|---|---|---|
| Use of 3 drafts | Refiner merges all 3 | Voter picks 1; refiner only edits the winner |
| Verifier sees | Paragraph short-summaries | **Full paragraph text** |
| Refiner role | Multi-source merger | Single-draft enhancer |
| Length budget | Implicit (300-500 words for baselines, no cap on Ours) | **Hard cap: 1000 words for everything** |
| Iteration | K=1 (single pass) | K=1 (single pass; iteration left as future work) |

## Status

Scaffolding stage. No production runs yet. Designed for an n=15
scout experiment to see if the architectural change moves $F_1$
beyond the v1/v2 ceiling.

## Quick start (when ready to run)

```bash
cd Refine-OneVision-Summary
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q          # smoke check
.venv/bin/python -m src.cli summarize <pdf_path>     # one-off
```

## Notes for the upcoming experiment

-  Run on the same 15-paper subset that we sample with seed=42
   (see `Evaluation/experiment/paper_pool.py`).
-  Use the existing `Evaluation/` module as the judge (both
   strict-LLM and DeBERTa modes), but with the new
   `Evaluation/src/scorer.py` that also reports F0.5
   (precision-weighted F-beta — missing facts hurt less).
-  Compare to: B1 Llama-70B-naive, B6 Llama-70B-v2prompt, and
   Ours-v2 (the existing 3-LLM-merge pipeline) on the same 15 papers.
