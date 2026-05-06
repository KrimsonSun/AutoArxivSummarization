# RefinedSummarization v2 — Coverage-Aware Architecture Changes

This document records the architectural changes made after the n=29
benchmark revealed that v1 of the pipeline produced summaries with
\textsuperscript{−0.20} F1 vs the strongest single-LLM baseline,
driven entirely by paper-side recall (0.24 vs 0.42). The full diagnosis
is in `paper/main.tex` §6.

## Summary of v1 → v2 changes

| # | What changed | Where | Why |
|---|---|---|---|
| 1 | Refiner system prompt rewritten for UNION-bias | `config/prompts.yaml:refiner.system` | v1 said "merge the strongest content" → biased to intersection of phrasings, dropped specific facts present in only 1–2 drafts |
| 2 | New `IssueType.COVERAGE_GAP` enum | `src/schemas/issue.py` | v1 verifier could only flag facts missing from ALL 3 drafts (`missing_info`); single-draft-only facts were invisible |
| 3 | Verifier system prompt teaches `coverage_gap` semantics + decision rules | `config/prompts.yaml:verifier.system` | gives the LLM the new vocabulary and how to choose between missing_info / coverage_gap / inconsistency |

No code changes are needed elsewhere — the new enum value flows through
existing serialization, and the prompt-only changes don't affect any
schema or function signature.

## Detailed change log

### Change 1: Refiner — UNION over intersection

**Before** (v1):
```
Your job is to produce ONE final summary that:
- Merges the strongest content from all three drafts.
- Corrects every factual_error using the cited evidence.
...
```

**After** (v2):
```
CORE PRINCIPLE — UNION, NOT INTERSECTION

Multi-agent debate yields three diverse drafts so that each agent's
blind spots are covered by the others. Your job is to PRESERVE the
UNION of specific facts across drafts, not to merge them down to a
common abstract phrasing. If only ONE of the three drafts mentions a
specific number, dataset, method name, or quantitative finding, and
that fact is supported by paper evidence, you MUST keep it.

Common failure modes to avoid:
-  Replacing "achieves 28.4 BLEU on WMT 2014 EN-DE" with "achieves
   state-of-the-art" because only one draft had the specific number.
-  Dropping a method component because two drafts didn't mention it.
-  Smoothing three different specific claims into one generic
   paraphrase to "merge" them.

Concretely, when integrating drafts:
-  Specific numerics → ALWAYS keep if at least one draft has them.
-  Named components / datasets / baselines → ALWAYS keep.
-  Concrete experimental findings → ALWAYS keep.
-  Abstract framing language → take the clearest single phrasing,
   not a vague conjunction.

Your job is to produce ONE final summary that:
-  Takes the UNION of specific facts from all three drafts.
-  Fills every missing_info AND coverage_gap by adding the fact.
-  Resolves every inconsistency by deferring to the evidence (drop
   the wrong number, keep the right one).
...
PREFER specificity over abstraction.
Aim for higher fact density: each non-trivial sentence should add
a specific verifiable fact, not just rephrase a thematic statement.
```

### Change 2: New `IssueType.COVERAGE_GAP`

**Schema change** (`src/schemas/issue.py`):
```python
class IssueType(str, Enum):
    FACTUAL_ERROR = "factual_error"
    MISSING_INFO = "missing_info"
    INCONSISTENCY = "inconsistency"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    AMBIGUITY = "ambiguity"
    COVERAGE_GAP = "coverage_gap"   # ← new in v2
```

This is a **strictly additive** change — existing JSON outputs from v1
verifier remain valid (they just don't use the new enum value).

### Change 3: Verifier teaches coverage_gap

Added to `config/prompts.yaml:verifier.system`:

```
- coverage_gap: ★ NEW — A SPECIFIC fact appears in 1 OR 2 of the 3
                drafts AND is supported by paper evidence, but not in
                all three. Tells the refiner "preserve this draft-only
                fact, do not merge it away." Prioritise raising these.

How to decide between coverage_gap, missing_info, and inconsistency:
-  Fact present in 0/3 drafts but in paper       → missing_info
-  Fact present in 1/3 or 2/3 drafts (consistent) → coverage_gap
-  Fact present in 2+ drafts but they disagree    → inconsistency
```

## Expected effect on metrics (hypothesis, untested as of this commit)

The four diagnostic mechanisms in `paper/main.tex` §6 predict that:

| Mechanism | v2 fix | Expected metric impact |
|---|---|---|
| (M1) Refiner intersection bias | Change 1 (prompt) | Recall ↑, Precision ≈, F1 ↑ |
| (M2) Verifier blindness to single-draft facts | Changes 2+3 | Recall ↑ (new issue type creates signal), F1 ↑ |
| (M3) No paper-side awareness | _not addressed in v2_ | — |
| (M4) Schema rewards abstraction | Refiner prompt (rule 5–6) | Marginal recall ↑ |

Quantitative target: lift F1 from 0.37 → ≥0.50 (strict-LLM mode), which
would put us above all single-LLM baselines except possibly B2 Qwen
(F1 0.57). M3 remains for v3.

## How to validate v2

1. Re-run the same 29-paper benchmark with the v2 pipeline.
2. The cached `outputs/experiment/papers/` PDFs and the cached
   `outputs/experiment/paper_claims/` claim sets in the Evaluation
   module should be re-used unchanged.
3. The new RefinedSummarization summaries will land at
   `outputs/experiment/summaries/<id>/Ours.json` (overwriting v1).
4. Re-run `experiment.run`, `strict_reeval --config config/strict.yaml`,
   `strict_reeval --config config/deberta.yaml`, then `experiment.plot`
   for all three modes.
5. Compare v1 vs v2 means; report Δ-F1 with bootstrap CI.

## Tests

All 23 unit + mocked-E2E tests pass after the schema + prompt changes:

```
$ cd RefinedSummarization && .venv/bin/python -m pytest tests/ -q
......................s.       [100%]
23 passed, 1 skipped in 12.12s
```

No tests reference the v1 refiner prompt verbatim, so the prompt rewrite
did not require test updates.
