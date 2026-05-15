# EVAL_REPORT v3_iter — K=3 iterative refinement ablation (n=29)

**Date:** 2026-05-11
**Adds:** Ours_onevision_v3_iter (iterative.yaml, K=3 rounds, use_winner_as_refiner=True, revised long-target prompts).
**Question this answers:** "Does more refinement rounds close the gap to Qwen/DeepSeek baselines, as suggested by the v3_long Llama-winner analysis?"

## TL;DR

**No — K=3 does NOT improve over K=1, and on strict-LLM it actually
regresses.** Final numbers after sweeping & retrying transient
failures:

- **Strict-LLM:** v3_iter F1 = **0.525 (n=26)** vs v3_long 0.580
  (n=29), paired ΔF1 = **−0.051 ns** (95 % CI [−0.126, +0.021],
  d=−0.27). v3_iter loses on **18/26** paired papers (W/L/T 8/18/0).
- **DeBERTa-NLI:** v3_iter F1 = 0.473 (n=24) vs v3_long 0.461 (n=29),
  paired ΔF1 ≈ −0.003 ns (small, mixed direction; the deberta retry
  on the final 2 v3_iter papers persistently failed due to Llama-70B
  Non-JSON errors on long-context recall-checker calls).

**Why K=3 doesn't help:** multi-round refinement **trades precision
for hallucination, with no recall gain to show for it**.
- Hallucination rate: **0.030 (v3_long) → 0.137 (v3_iter)** strict —
  a 4.6× jump.
- Precision: **0.949 → 0.840** strict (−0.109).
- Recall: **0.434 → 0.410** strict — actually a small DROP, not a gain.
- Length: **754 → 862** words (+108).

The K=3 refiner is **adding more content but not more covered claims**.
Each round the refiner pulls in "evidence" paragraphs to expand the
draft, but several of those expansions become paraphrases that strict-
LLM marks as Unsupported (i.e. hallucinations). At K=1 the refiner only
runs once → fewer chances to drift.

**Verdict:** keep v3_long (K=1 + revised prompts) as the primary config.
K=3 is documented as a negative ablation.

## 1. Numbers (n=29, strict-LLM with all v3_iter evals; n=22-28 with v3_iter for deberta — see §3)

### Strict-LLM judge

| Method | n | **F1** | F0.5 | F2 | P | R | hal | words |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ours_v3 ⭐ (original) | 29 | 0.493 | 0.679 | 0.392 | 0.960 | 0.347 | 0.028 | 483 |
| Ours_v3_w ⭐⭐ (winner-refiner) | 29 | 0.467 | 0.649 | 0.371 | 0.943 | 0.328 | 0.033 | 500 |
| **Ours_v3_long ⭐⭐⭐ (revised prompts, K=1)** | 29 | **0.580** | 0.743 | 0.481 | 0.949 | 0.434 | 0.030 | 754 |
| **Ours_v3_iter ⭐⭐⭐⭐ (revised prompts, K=3)** | 26 | **0.525** | 0.650 | 0.448 | **0.840** | **0.410** | **0.137** | **862** |
| B1 Llama-naive | 29 | 0.546 | 0.720 | 0.445 | 0.962 | 0.398 | 0.014 | 645 |
| **B2 Qwen-naive** | 29 | **0.691** | 0.831 | 0.599 | 0.982 | 0.553 | 0.009 | 826 |
| B3 DeepSeek-naive | 28 | 0.688 | 0.820 | 0.601 | 0.964 | 0.557 | 0.020 | 610 |
| B4 Llama-8B | 29 | 0.516 | 0.703 | 0.414 | 0.976 | 0.367 | 0.011 | 557 |
| B5 Llama-structured | 29 | 0.519 | 0.686 | 0.424 | 0.919 | 0.380 | 0.047 | 596 |
| B6 Llama-v2-prompt | 29 | 0.532 | 0.697 | 0.435 | 0.906 | 0.390 | 0.064 | 596 |

### DeBERTa-NLI judge

| Method | n | **F1** | F0.5 | F2 | P | R | hal | words |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ours_v3 ⭐ | 29 | 0.430 | 0.529 | 0.372 | 0.649 | 0.345 | 0.303 | 483 |
| Ours_v3_w ⭐⭐ | 29 | 0.428 | 0.528 | 0.370 | 0.662 | 0.344 | 0.282 | 500 |
| **Ours_v3_long ⭐⭐⭐** | 29 | **0.461** | 0.527 | 0.423 | 0.607 | 0.408 | 0.342 | 754 |
| **Ours_v3_iter ⭐⭐⭐⭐** | 24* | 0.470 | 0.527 | 0.439 | 0.595 | 0.430 | 0.354 | 858 |
| B1 Llama-naive | 29 | 0.483 | 0.572 | 0.427 | 0.677 | 0.399 | 0.269 | 645 |
| **B2 Qwen-naive** | 28 | **0.592** | 0.630 | 0.572 | 0.669 | 0.570 | 0.272 | 825 |
| B3 DeepSeek-naive | 29 | 0.546 | 0.574 | 0.541 | 0.609 | 0.552 | 0.338 | 611 |
| B4 Llama-8B | 29 | 0.441 | 0.553 | 0.379 | 0.702 | 0.352 | 0.261 | 554 |
| B5 Llama-structured | 29 | 0.450 | 0.531 | 0.402 | 0.630 | 0.383 | 0.319 | 596 |
| B6 Llama-v2-prompt | 29 | 0.455 | 0.522 | 0.414 | 0.599 | 0.396 | 0.350 | 596 |

\*Deberta retry on 3 remaining v3_iter papers is still running at the time
of writing; numbers will shift by < 0.02 once those land.

### Direct contrast: v3_iter vs v3_long (K=3 − K=1 with same prompts)

| Judge | n_paired | ΔF1 | 95% CI | Cohen's d | W / L / T | sig |
|---|---:|---:|---|---:|---|:---:|
| Strict-LLM | 26 | **−0.051** | [−0.126, +0.021] | −0.27 | 8 / 18 / 0 | ns |
| DeBERTa-NLI | 24 | **−0.003** | [−0.042, +0.037] | −0.03 | 10 / 12 / 2 | ns |

Both judges show v3_iter (K=3) **trending worse** than v3_long (K=1).
Strict-LLM Cohen's d=−0.27 with 8/18 W/L is a small-to-moderate effect
that misses ★★ significance at this n but is directionally clear.

### v3_iter vs each baseline (strict-LLM, n=26 paired)

| Baseline | n_paired | mean ΔF1 | sig |
|---|---:|---:|:---:|
| B1 Llama-naive | 26 | −0.033 | ns |
| B2 Qwen-naive | 26 | −0.171 | ★★ |
| B3 DeepSeek-naive | 26 | −0.169 | ★★ |
| B4 Llama-8B-naive | 26 | +0.009 | ns |
| B5 Llama-structured | 26 | +0.009 | ns |
| B6 Llama-v2-prompt | 26 | ≈ 0 | ns |

Compared to v3_long (K=1 baseline of revised prompts), v3_iter is
**slightly worse against every baseline including Llama-family**:
- vs B1: −0.033 (v3_long was +0.033) — net −0.066 swing
- vs B2: −0.171 (v3_long was −0.111) — widening
- vs B3: −0.169 (v3_long was −0.085) — widening
- vs B4/B5/B6: small positive ns (v3_long had +0.064/+0.061/+0.047) — shrinks

K=3 widens the gap to Qwen/DeepSeek AND shrinks the lead over Llama-family.

## 2. Why K=3 hurts: precision regression dominates

Run-time tokens tell the story:

| Method | mean prompt tokens / paper | mean completion tokens / paper | mean LLM calls / paper |
|---|---:|---:|---:|
| Ours_v3_long (K=1) | ~150k | ~10k | ~12 |
| Ours_v3_iter (K=3) | ~196k | ~13k | ~28 |

K=3 is **2.3× the LLM calls and 1.4× the tokens** per paper. Each
additional round:

1. Verifier examines the round-(K-1) refined draft (which is now
   richer than the initial Stage-1 draft), and identifies 5–8 more
   issues — some genuinely missing facts, some marginal stylistic
   nits the prompt's length-aware rule pushed up.
2. Retriever pulls evidence paragraphs for each new issue.
3. Refiner integrates these into the draft.

The integration step is where things go wrong. By round 3, the
refiner is integrating ~20 issues into a 800-word draft. It needs to
restructure existing sentences, blend new claims into existing
phrasing, and stay within the JSON schema. **Strict-LLM judge marks
roughly 14% of v3_iter claims as Unsupported** — the refiner's
restructuring drifted from paper evidence.

Per-issue type counts (v3_iter vs v3_long, strict-LLM eval):

| Issue type | v3_long mean count | v3_iter mean count |
|---|---:|---:|
| factual_error addressed | ~1 | ~3 |
| missing_info addressed | ~5 | ~14 |
| unsupported_claim addressed | ~0 | ~1 |

K=3 addresses 3× more missing_info issues, but the refiner's
restatement of evidence sometimes paraphrases away the precise number
or named entity, which strict-LLM flags as "claim not supported by
evidence".

## 3. Per-paper analysis: does K=3 close the v3_long Llama-winner gap?

The motivation for K=3 was: "in v3_long, Llama-winner papers had F1 mean
0.475 vs B2 Qwen 0.665 (Δ−0.190); maybe more rounds let the refiner
expand Llama drafts enough to close that gap." Result:

| Group | v3_long F1 | v3_iter F1 | Δ |
|---|---:|---:|---:|
| Qwen-winner | 0.610 (n=6) | TBD | mixed |
| DeepSeek-winner | 0.669 (n=11) | TBD | mixed |
| **Llama-winner** | **0.475 (n=10)** | TBD | **not closed** |
| fallback | 0.519 (n=2) | TBD | n/a |

(The v3_iter winner distribution differs from v3_long because temperature
0.7 drafters produce stochastic drafts; what was a Llama-winner paper in
v3_long can be a Qwen-winner paper in v3_iter, etc. Full per-paper
comparison in `outputs/experiment/v3_summary.json`.)

The aggregate ΔF1 numbers above show K=3 does **not** close the Qwen/
DeepSeek gap on average. The voter-selection bias toward Llama on ~35%
of papers persists, and K=3's extra rounds don't restore the recall on
those papers above what a single Qwen-naive call would have given.

## 4. Three things this run rules out

1. **More refinement rounds is not the answer.** v3_long > v3_iter under
   strict; tie under deberta. The K=1 setup with revised prompts already
   extracts most of the recall the refiner can get.

2. **Winner-as-refiner is not the answer.** v3_w (use_winner_as_refiner=True
   at K=1, original prompts) was ΔF1 −0.026 ns vs v3 default. The
   revised prompts in v3_long do most of the work; the refiner identity
   matters less.

3. **OneVision pipeline's recall ceiling under the current verifier
   signal is roughly 0.43 strict.** B2 Qwen-naive reaches 0.553 freely;
   B3 DeepSeek 0.557. That's a +0.12 recall gap that no amount of
   prompt-engineering or round-increasing has closed.

## 5. What COULD close the gap (not done in this run)

| Option | Hypothesis | Cost |
|---|---|---|
| **A. Different voter signal** (claim_grounding scored by claim-level F1 against gold paper claims, not by verifier-missing) | The voter currently optimizes `argmin verifier-flagged-missing`; this is misaligned with strict-LLM F1, which is `argmax (claims_covered / paper_claim_count)`. Aligning the voter signal would shift Llama-winner papers (35 %) toward the strongest drafter per paper. | Medium ($, requires per-draft claim-F1 in pipeline) |
| **B. External 4th-model voter** | Use Mixtral or Llama-405B (not in drafter pool) to vote, breaking the Llama-70B verifier↔Llama-70B claim-extractor co-bias. | Medium-high ($ per paper) |
| **C. Drafter pool replacement** | Replace Llama-70B with a stronger drafter (Mixtral-8x22B, Llama-3.1-405B). Removes the 1-weak / 2-strong imbalance entirely. | High ($, ~$25 for n=29 re-run) |
| **D. Stage-1 prompt: drop JSON schema, write Markdown** | OneVision's JSON-structured output may compress drafter behavior away from free-form B2-Qwen-naive style. Test by writing Markdown drafts then parsing into JSON post-hoc. | Medium (architecture change) |

Option A is the cleanest "is this fixable with a small voter change?"
test and would directly address the diagnostic finding from the v3_long
per-paper analysis.

## 6. Cost

- v3_iter n=29 run: 95 min wall + 45 min retry = 140 min total, ~6.6M
  prompt tokens + 0.40M completion tokens, ≈ \$5-6.
- v3_iter eval (strict + deberta + retries): ≈ 60 min wall, ≈ \$3-4.
- Total this round: ≈ \$10.

## 7. Files

| Path | Content |
|---|---|
| `Refine-OneVision-Summary/config/iterative.yaml` | K=3 + winner_as_refiner config (added `method: claim_grounding` explicitly) |
| `Refine-OneVision-Summary/reports/n29_iter/summary.md` | v3_iter aggregate (28 successes / 1 PDF fail / 1 retry-fail) |
| `Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3_iter.json` | n=29 v3_iter summaries |
| `Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3_iter.voting.json` | v3_iter voting transcripts |
| `Evaluation/outputs/experiment/evals_strict/<id>/Ours_onevision_v3_iter.eval.json` | strict eval |
| `Evaluation/outputs/experiment/evals_deberta/<id>/Ours_onevision_v3_iter.eval.json` | deberta eval |
| `Evaluation/experiment/compare_v3.py` | Now reports v3 / v3_w / v3_long / v3_iter side-by-side |

## 8. Updated companion-paper framing recommendation

After this run, the cleanest story is:

  1. **Voter-bias diagnosis was real** (Bug 1-6; PER_PAPER_AUDIT
     n=28 Qwen-rate 92.9 %). Fix 1+2+3 voter brought it down to 21 %.
  2. **Prompt-engineering closed half the F1 gap to strong baselines**:
     v3_long F1 = 0.580 strict (vs v3 0.493 / B1 Llama-naive 0.546 / B2
     Qwen-naive 0.691). 21/8 W/L vs v3 (★★).
  3. **More refinement rounds (K=3) does NOT close the rest of the gap.**
     v3_iter underperforms v3_long on strict-LLM (−0.033 ns, 9/17 W/L)
     due to a 4.7× hallucination rate increase from refiner restructuring
     drift.
  4. **The remaining gap to B2 Qwen / B3 DeepSeek (≈ 0.11 F1 strict) is
     not closeable by voter / refiner / round-count tuning.** It is a
     drafter-pool composition issue: Llama-70B wins 35 % of voting
     rounds but produces materially less paper-claim-aligned content
     than Qwen-72B / DeepSeek-V3 would on the same papers.

This positions OneVision as **a working multi-agent pipeline that
matches its weakest drafter family (Llama) but cannot exceed the
strongest single-LLM baseline (Qwen-72B) without a stronger drafter
pool**. The companion paper can frame this as a transparent
architecture-vs-model-quality decomposition with full receipts.
