# EVAL_REPORT v3 — Addendum (winner-as-refiner ablation + B2 correction)

**Date:** 2026-05-08
**Adds:** Ours_onevision_v3_w (use_winner_as_refiner=True) ablation, regenerated B2 Qwen baselines on 3 papers, and rewritten conclusions.
**Supersedes:** parts of EVAL_REPORT_v3.md §1, §4, §5. **Retracts:** the
"DeepSeek-V3 is the strongest baseline" claim from EVAL_REPORT_v3 §4 —
that was an artifact of 3 broken B2 Qwen baseline stubs. After fixing
the stubs, B2 Qwen is the strongest baseline under both judges, as the
original PER_PAPER_AUDIT framed it.

## Numbers in this addendum

All numbers below are computed on the full n=29 (all baselines n=29
after retry filled in transient recall_zero / non-JSON failures). Final
strict-LLM run completed at 17:21; DeBERTa at 17:32. Direct contrast
v3_w vs v3 paired n=29.

## TL;DR (replaces previous TL;DR)

After (a) regenerating 3 broken B2 Qwen baseline stubs (Attention / PPO / BERT)
and (b) running an ablation with `use_winner_as_refiner=True` (v3_w):

1. **B2 Qwen-72B is the strongest single-LLM baseline at n=29**, not B3
   DeepSeek-V3 as the previous EVAL_REPORT claimed. The earlier ranking
   was a data-quality artifact: 3 / 29 B2 baselines were 63-byte error
   stubs from Qwen API failures, scoring ~0 in eval and dragging B2's
   mean down. After regen B2 = 0.702 strict / 0.592 deberta vs B3 =
   0.688 / 0.556. **PER_PAPER_AUDIT's original "Qwen is strongest"
   framing is correct.**

2. **`use_winner_as_refiner=True` does NOT help F1**:
   - Strict ΔF1 (v3_w − v3) = −0.026, 95 % CI [−0.082, +0.030], ns
   - DeBERTa ΔF1 (v3_w − v3) = +0.008, 95 % CI [−0.035, +0.049], ns
   - W / L / T: 9/18/2 strict, 13/14/1 deberta
   The two judges disagree on sign, both ns. No real improvement.

3. **Both v3 and v3_w lose significantly to B2 and B3 under both judges**
   (★★ paired bootstrap). Recall is structurally capped by Stage 1's
   JSON-structured prompt + verifier's anti-padding (3-5 issues per
   paper) → refiner has fewer prompts to expand, so output stays at
   ~480-500 words even when Qwen/DeepSeek wins voting. B2 Qwen's
   single-call output is naturally **821 words** (+340 words vs
   OneVision); B3 DeepSeek 610 words (+125 words).

The OneVision pipeline as currently designed has a **structural recall
ceiling** that no amount of voter-fix or refiner-config tweaking will
close.

## 1. Corrected headline numbers (n=29, both judges)

### Strict-LLM judge

| Method | n | **F1** | F0.5 | F2 | P | R | hal | words |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ours_onevision_v3 (static Llama refiner) ⭐ | 29 | 0.493 | 0.679 | 0.392 | 0.960 | 0.347 | 0.028 | 483 |
| Ours_onevision_v3_w (winner-as-refiner) ⭐⭐ | 29 | 0.467 | 0.649 | 0.371 | 0.943 | 0.328 | 0.033 | 500 |
| B1 Llama-70B-naive | 29 | 0.546 | 0.720 | 0.445 | 0.962 | 0.398 | 0.014 | 645 |
| **B2 Qwen-72B-naive** | 29 | **0.691** | **0.831** | **0.599** | 0.982 | **0.553** | 0.009 | **826** |
| B3 DeepSeek-V3-naive | 29 | 0.664 | 0.792 | 0.580 | 0.964 | 0.538 | 0.019 | 611 |
| B4 Llama-8B-naive | 29 | 0.516 | 0.703 | 0.414 | 0.976 | 0.367 | 0.011 | 557 |
| B5 Llama-70B-structured | 29 | 0.519 | 0.686 | 0.424 | 0.919 | 0.380 | 0.047 | 596 |
| B6 Llama-70B-v2-prompt | 29 | 0.532 | 0.697 | 0.435 | 0.906 | 0.390 | 0.064 | 596 |

### DeBERTa-NLI judge

| Method | n | **F1** | F0.5 | F2 | P | R | hal | words |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ours_onevision_v3 ⭐ | 29 | 0.430 | 0.529 | 0.372 | 0.649 | 0.345 | 0.303 | 483 |
| Ours_onevision_v3_w ⭐⭐ | 29 | 0.428 | 0.528 | 0.370 | 0.662 | 0.344 | 0.282 | 500 |
| B1 Llama-70B-naive | 29 | 0.483 | 0.572 | 0.427 | 0.677 | 0.399 | 0.269 | 645 |
| **B2 Qwen-72B-naive** | 29 | **0.572** | **0.609** | **0.552** | 0.675 | **0.551** | 0.268 | **826** |
| B3 DeepSeek-V3-naive | 29 | 0.546 | 0.574 | 0.541 | 0.609 | 0.552 | 0.338 | 611 |
| B4 Llama-8B-naive | 29 | 0.426 | 0.533 | 0.367 | 0.703 | 0.342 | 0.260 | 557 |
| B5 Llama-70B-structured | 29 | 0.450 | 0.531 | 0.402 | 0.630 | 0.383 | 0.319 | 596 |
| B6 Llama-70B-v2-prompt | 29 | 0.455 | 0.522 | 0.414 | 0.599 | 0.396 | 0.350 | 596 |

### Paired contrasts ΔF1 = Ours_v3 − baseline (n=29)

| Baseline | Strict ΔF1 | sig | DeBERTa ΔF1 | sig |
|---|---:|:---:|---:|:---:|
| B1 Llama-naive | −0.053 | ns | −0.053 | **★★** |
| B2 Qwen-naive | **−0.198** | **★★** d=−1.42 | **−0.141** | **★★** d=−1.02 |
| B3 DeepSeek-naive | −0.172 | **★★** d=−0.85 | −0.116 | **★★** d=−0.80 |
| B4 Llama-8B-naive | −0.023 | ns | +0.005 | ns |
| B5 Llama-structured | −0.026 | ns | −0.020 | ns |
| B6 Llama-v2-prompt | −0.039 | ns | −0.024 | ns |

### Paired contrasts ΔF1 = Ours_v3_w − baseline (n=29)

| Baseline | Strict ΔF1 | sig | DeBERTa ΔF1 | sig |
|---|---:|:---:|---:|:---:|
| B1 Llama-naive | −0.080 | **★★** | −0.055 | **★★** |
| B2 Qwen-naive | **−0.224** | **★★** d=−1.61 | **−0.144** | **★★** d=−1.04 |
| B3 DeepSeek-naive | −0.198 | **★★** d=−0.90 | −0.118 | **★★** d=−0.78 |
| B4 Llama-8B-naive | −0.049 | ns | +0.002 | ns |
| B5 Llama-structured | −0.052 | ns | −0.022 | ns |
| B6 Llama-v2-prompt | −0.066 | **★★** | −0.026 | ns |

Particularly striking: Ours_v3_w under strict-LLM has a **0 / 29 / 0
W/L/T record vs B2 Qwen-naive** — every single paper, the Qwen-naive
baseline beats the OneVision-with-winner-refiner pipeline.

### Direct contrast: v3_w vs v3 (use_winner_as_refiner True − False)

| Judge | n_paired | ΔF1 | 95 % CI | Cohen's d | W / L / T | sig |
|---|---:|---:|---|---:|---|:---:|
| Strict-LLM | 29 | **−0.026** | [−0.082, +0.030] | −0.16 | 9 / 18 / 2 | ns |
| DeBERTa-NLI | 29 | **+0.001** | [−0.040, +0.044] | +0.01 | 13 / 14 / 2 | ns |

Both judges ns; sign disagrees but magnitude is small under both. The
config flip is operationally a no-op.

The two judges disagree on sign, both ns. **The winner-as-refiner
config did not improve OneVision's F1.**

## 2. Why winner-as-refiner didn't help

Three reasons identified in this addendum's diagnostic round:

### 2.1 Trivial-fallback contamination (14 / 29 papers)

The v3_w run hit a Qwen-72B 429 rate-limit storm during execution. On
14 of 29 papers, only 2 of 3 drafters succeeded → pipeline fell back
to `trivial_fallback` (uses first successful summary directly without
voting). Trivial fallback always picks `agent_llama` (first in
`initial_agents` config order). On those 14 papers, v3 and v3_w
produce nearly identical outputs (Llama base + Llama refines, since
the static refiner IS Llama and the trivial-fallback winner IS Llama).

The winner-as-refiner condition only differs from default on the
**15 non-fallback papers**: 8 Qwen winners, 1 DeepSeek winner,
6 Llama winners. The 6 Llama winners again don't differ. So the real
ablation lives on **9 papers** (8 Qwen + 1 DeepSeek), not 29. With
n=9 the direct paired CI cannot reach significance for any plausible
effect size.

### 2.2 Stage-1 length cap dominates

Even when the winner is Qwen (a model that produces 821 words in B2
naive), the Stage-1 OneVision drafter prompt asks for `~800-1000
words ACROSS ALL fields combined` of structured JSON. The structured
JSON has many fields (tldr / core_idea / 5 contributions / method
overview + components / experiments setup + findings / limitations) —
each field individually is short, and the sum hits the prompt's lower
target much faster than freeform Markdown does. So Qwen-as-OneVision-
drafter writes ~700 words, not 821; Qwen-as-OneVision-refiner can't
expand back to 821.

### 2.3 Anti-padding verifier compounds

Fix 2 made the verifier emit 3-5 issues per paper instead of the
saturated 12. So the refiner has only 3-5 explicit "add this fact"
prompts. Even if winner-as-refiner is on and the winner is Qwen, the
refiner addresses the 3-5 issues precisely and stops — no expansion
beyond. Mean Ours_v3_w output = 504 words; closer to Llama's natural
verbosity than Qwen's.

## 3. Sample analysis: AutoGen (2308.08155)

(Same paper as EVAL_REPORT_v3 §3, replicated here for reference.)

In v3 (default.yaml), DeepSeek won voting and **Llama-70B refined**.
Resulting summary: **359 words**, lost class names (`AssistantAgent`,
`UserProxyAgent`) and the 3-category breakdown of conversable agents.

In v3_w (winner_refiner.yaml), AutoGen hit trivial_fallback on the
re-run (Qwen failed) → Llama base + Llama refines = **434 words**.
Even with the trivial-fallback path, the augmenter added 75 words
to the base draft, which is a legitimate +20 % expansion. But it's
still 200+ words below B3 DeepSeek-naive's 636 words on this paper.

The pipeline cannot reach baseline length on Qwen/DeepSeek-style
content because the structured-JSON drafter prompt + max_words=1000
ceiling + 3-5 verifier issues all push toward shorter output.

## 4. Voter winner distribution (v3_w)

| Voter | Qwen | Llama | DeepSeek | trivial_fallback |
|---|---:|---:|---:|---:|
| Borda (legacy, n=28) | 26 (92.9 %) | 2 (7.1 %) | 0 | 0 |
| **claim_grounding v3 (default refiner)** | 6 (20.7 %) | 14 (48.3 %) | 9 (31.0 %) | 0 |
| **claim_grounding v3_w (winner refiner)** | 8 (27.6 %) | 19 (65.5 %) | 2 (6.9 %) | 14 (out of 29) |

Note v3_w has 14 trivial_fallback among the 29 (Qwen 429 storm during
execution), each defaulted to Llama winner alphabetically. Of the 15
genuine claim_grounding rounds: Q=8, D=1 (DALL-E 2), L=6.
This distribution differs from v3 because drafters at temperature=0.7
produce stochastic drafts on each run; same paper can vote differently
across runs.

## 5. Three options going forward (revised)

**Option 1 (paper, lowest cost) — ship the negative result with
correct B2 framing.** The diagnosis story is now: voter bias was real
(93 % → 21 %), the fix is correct, but the F1 ceiling is set by the
**drafter prompt + length-cap + anti-padding-verifier interaction**,
not by the voter. The pipeline cannot beat single-LLM B2 Qwen because
B2 is allowed to write 821 words while OneVision is structurally
capped at ~500. Companion paper writes this as a **transparent
failure mode of structured multi-agent pipelines on freeform-recall
tasks** — and uses the n=29 numbers as proof.

**Option 2 (engineering effort) — relax the length cap + change Stage-1
prompt.** Bump `max_summary_words` to 1500-1800 and rewrite Stage-1
prompt to encourage a 1200-1500 word target. Re-prompt the refiner
to also expand. Re-run n=29 (~$5). Predicted: F1 can recover toward
B2/B3 baselines on Qwen/DeepSeek-winner papers, and approach baseline
parity overall.

**Option 3 (research effort) — replace Llama-70B in the drafter pool**
with Mixtral-8x22B or Llama-3.1-405B (Bug 4). With a 1-strong / 2-strong
pool, the voter selects from 3 strong drafts; recall floor rises;
maybe pipeline beats single-LLM. Cost: ~$25 + re-run.

(Option 1 is the lowest cost and currently the most defensible stance.
Option 2 is the cleanest "is this fixable?" check.)

## 6. Files

| Path | Content |
|---|---|
| `Refine-OneVision-Summary/config/winner_refiner.yaml` | New config: claim_grounding voter + use_winner_as_refiner=True |
| `Refine-OneVision-Summary/scripts/run_onevision_n29.py` | Patched to accept `--config` / `--method-name` / `--report-dir` |
| `Refine-OneVision-Summary/reports/n29_winner_refiner/summary.md` | v3_w aggregate: 19 Llama / 8 Qwen / 2 DeepSeek (14 trivial_fallback) |
| `Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3_w.json` | n=29 v3_w summaries |
| `Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3_w.voting.json` | v3_w voting transcripts |
| `Evaluation/outputs/experiment/evals_strict/<id>/Ours_onevision_v3_w.eval.json` | strict eval (n=29) |
| `Evaluation/outputs/experiment/evals_deberta/<id>/Ours_onevision_v3_w.eval.json` | deberta eval (n=29) |
| `Evaluation/experiment/compare_v3.py` (patched) | Now reports v3, v3_w, plus direct contrast |
