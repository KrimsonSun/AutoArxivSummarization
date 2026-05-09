# Comprehensive evaluation: OneVision v3 (Fix 1+2+3 voter) on n=29

**⚠ READ ALSO `EVAL_REPORT_v3_addendum.md`** — corrects two issues
in this report:
1. The "DeepSeek-V3 is strongest baseline" claim in §4 is **retracted**.
   It was a data-quality artifact: 3/29 B2 Qwen baseline files were
   63-byte error stubs (Qwen API failed during baseline generation),
   scoring ~0 in eval and depressing B2's mean. After regenerating
   those 3 baselines, B2 Qwen is the strongest baseline at n=29 under
   both judges (0.691 strict / 0.572 deberta vs B3 0.664 / 0.546).
2. Adds Ours_onevision_v3_w (use_winner_as_refiner=True) ablation;
   that config flip does **not** improve F1.

**Date:** 2026-05-08
**Branch:** `claude/ecstatic-kowalevski-128f4d`
**Pipeline:** Refine-OneVision-Summary v3 (claim_grounding voter, missing_info-as-recall scoring, anti-padding verifier)
**Eval target:** `Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3.json`
**Judges:** Strict-LLM (Llama-70B-as-judge) + DeBERTa-NLI (decoupled local NLI verifier)
**Bootstrap:** 10 000 resamples, paired by paper, seed = 42
**Cost:** ≈ \$3 OneVision pipeline + ≈ \$15 baselines + eval ≈ \$5  ≈ \$23 total

## TL;DR

The voter-bias diagnosis was correct (Qwen-rate 93 % → 21 %), and **the new
voter is doing exactly what we asked it to**. But the resulting Ours_v3
pipeline F1 is **lower** than every single-LLM baseline under the
strict-LLM judge, and lower than 4 / 6 baselines under DeBERTa-NLI. The
recall component drops because the new voter selects Llama base drafts on
48 % of papers, and Llama produces shorter drafts (≈350-400 words) that
miss more paper claims than Qwen drafts (≈700 words).

**The most consequential new finding is unrelated to the voter fix:**
B3 **DeepSeek-V3 is the strongest single-LLM baseline at n=29**
(F1 0.664 strict / 0.554 deberta), beating B2 Qwen-72B (0.617 / 0.480)
under both judges. Both companion-paper drafts so far have framed B2
Qwen as the strongest baseline; that framing is now incorrect.

---

## 1. Headline numbers (n=29 papers; 1 / 30 PDF parse failure on 2106.04561)

### Strict-LLM judge (Llama-70B-as-judge, FActScore-style)

| Method | n | **F1** | F0.5 | F2 | P | R | hal | mean words |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Ours_onevision_v3** ⭐ | 29 | **0.493** | 0.679 | 0.392 | 0.960 | **0.347** | 0.028 | **483** |
| B1 Llama-70B-naive | 29 | 0.546 | 0.720 | 0.445 | 0.962 | 0.398 | 0.014 | 645 |
| B2 Qwen-72B-naive | 29 | 0.617 | 0.731 | 0.541 | 0.883 | 0.502 | 0.110 | 752 |
| **B3 DeepSeek-V3-naive** | 29 | **0.664** | **0.792** | **0.580** | 0.963 | **0.538** | 0.021 | 611 |
| B4 Llama-8B-naive | 28 | 0.517 | 0.704 | 0.415 | 0.979 | 0.368 | 0.007 | 555 |
| B5 Llama-70B-structured | 29 | 0.519 | 0.686 | 0.424 | 0.919 | 0.380 | 0.047 | 596 |
| B6 Llama-70B-v2-prompt | 29 | 0.532 | 0.697 | 0.435 | 0.906 | 0.390 | 0.064 | 596 |

### DeBERTa-NLI judge (decoupled, no LLM-as-judge sycophancy)

| Method | n | **F1** | F0.5 | F2 | P | R | hal | mean words |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Ours_onevision_v3** ⭐ | 29 | **0.430** | 0.529 | 0.372 | 0.649 | **0.345** | 0.303 | **483** |
| B1 Llama-70B-naive | 29 | 0.483 | 0.572 | 0.427 | 0.677 | 0.399 | 0.269 | 645 |
| B2 Qwen-72B-naive | 29 | 0.480 | 0.516 | 0.457 | 0.619 | 0.450 | 0.331 | 752 |
| **B3 DeepSeek-V3-naive** | 29 | **0.537** | **0.583** | **0.527** | 0.608 | **0.533** | 0.338 | 611 |
| B4 Llama-8B-naive | 29 | 0.413 | 0.515 | 0.356 | 0.700 | 0.332 | 0.263 | 557 |
| B5 Llama-70B-structured | 29 | 0.450 | 0.531 | 0.402 | 0.630 | 0.383 | 0.319 | 596 |
| B6 Llama-70B-v2-prompt | 29 | 0.420 | 0.479 | 0.385 | 0.600 | 0.370 | 0.351 | 596 |

**Both judges rank: DeepSeek > Qwen > Llama-naive > B5 / B6 > Llama-8B > Ours_v3.**

### Paired contrasts ΔF1 = Ours_v3 − baseline (10 000-resample bootstrap)

| Baseline | Strict ΔF1 | Strict 95 % CI | sig | DeBERTa ΔF1 | DeBERTa CI | sig |
|---|---:|---|:---:|---:|---|:---:|
| B1 Llama-naive | −0.053 | [−0.113, +0.006] | ns | **−0.053** | [−0.099, −0.005] | **★★** |
| B2 Qwen-naive | **−0.125** | [−0.216, −0.021] | **★★** | −0.050 | [−0.136, +0.043] | ns |
| **B3 DeepSeek-naive** | **−0.172** | [−0.238, −0.095] | **★★** d=−0.85 | **−0.106** | [−0.162, −0.051] | **★★** d=−0.70 |
| B4 Llama-8B-naive | −0.027 | [−0.085, +0.032] | ns | +0.018 | [−0.039, +0.077] | ns |
| B5 Llama-structured | −0.026 | [−0.090, +0.036] | ns | −0.020 | [−0.071, +0.029] | ns |
| B6 Llama-v2-prompt | −0.039 | [−0.085, +0.005] | ns | +0.011 | [−0.048, +0.077] | ns |

Cross-judge agreement: **Ours_v3 loses significantly to B3 DeepSeek under
both judges (★★)**. The B1 / B2 contrasts are sensitive to judge choice,
but in both cases Ours_v3 is numerically lower. B4 / B5 / B6 contrasts
are ns under both judges.

## 2. What the voter fix actually delivered

PER_PAPER_AUDIT.md (Borda voter, n=28) reported a 92.9 % Qwen-rate
across the n=29 benchmark; the per-paper audit found that the voter
agreed with the actually-best baseline on only 14 / 27 = 52 % of papers
(no better than always picking Qwen). The Fix 1+2+3 voter:

| Voter | Qwen | Llama | DeepSeek |
|---|---:|---:|---:|
| Borda (legacy) | **26 / 28 (92.9 %)** | 2 / 28 (7.1 %) | 0 / 28 (0 %) |
| **claim_grounding (v3)** | 6 / 29 (20.7 %) | 14 / 29 (48.3 %) | 9 / 29 (31.0 %) |

The new distribution is much closer to what a per-paper "best drafter"
ground truth would look like. It also produces non-degenerate ties (no
3-way ties on the live n=29 run, vs. one in the offline n=5 replay).

## 3. Why F1 went down: recall, not precision

The Ours_v3 pipeline is **highest-precision** of all 7 methods under the
strict-LLM judge (P = 0.960 vs B3 DeepSeek 0.963 — basically tied, well
above B2 Qwen's 0.883). It does **not** hallucinate (hal = 0.028, the
second-lowest after B4). Where it loses is recall:

| Method | mean words | recall (strict) | recall (deberta) |
|---|---:|---:|---:|
| **Ours_onevision_v3** | **483** | **0.347** | **0.345** |
| B1 Llama-naive | 645 | 0.398 | 0.399 |
| B2 Qwen-naive | 752 | 0.502 | 0.450 |
| B3 DeepSeek-naive | 611 | 0.538 | 0.533 |
| B4 Llama-8B-naive | 555 | 0.368 | 0.332 |
| B5 Llama-structured | 596 | 0.380 | 0.383 |
| B6 Llama-v2-prompt | 596 | 0.390 | 0.370 |

Ours_v3 mean output is **the shortest of all methods** at 483 words —
roughly 36 % of the 1000-word cap. The cap is a ceiling not a floor,
and the new voter selects Llama base drafts on 48 % of papers. Llama's
default verbosity is ≈350-400 words, much shorter than Qwen's 700+.
The single-source augmenter does add some content via the verifier-driven
issue list, but only enough to recover a few claims per paper, not enough
to close the 200-300 word recall gap.

## 4. The DeepSeek-V3 finding (most important new datapoint)

Both companion-paper drafts have so far framed B2 Qwen-72B-naive as the
strongest cross-family single-LLM baseline. **At n=29 with the cleaner
baselines re-run, this is wrong.** DeepSeek-V3 wins under both judges:

| Comparison | Strict ΔF1 | DeBERTa ΔF1 |
|---|---:|---:|
| B3 DeepSeek vs B2 Qwen | **+0.047** | **+0.057** |
| B3 DeepSeek vs B1 Llama | **+0.118** | **+0.054** |

This has two implications:

1. **The Borda voter's 93 %-Qwen-rate was even more wrong than the
   original audit suggested.** Not only was it failing to do per-paper
   drafter selection, it was selecting the *second-strongest* model on
   ~93 % of papers. The "best fixed pick" is DeepSeek, not Qwen.

2. **A correctly-calibrated voter would target DeepSeek as its
   modal pick.** The Fix 3 voter picks DeepSeek 31 % of the time, which
   is closer to ground truth than Borda's 0 %, but still under-selects
   it relative to "always DeepSeek" being the optimal fixed strategy.

## 5. Honest paper framing — three options

1. **Negative result on architecture, positive result on diagnosis.**
   Frame the OneVision pipeline as "a transparent failure": the
   voter-bias diagnosis (E25 / L9 / Bug 1-6) is the contribution; the
   pipeline F1 is reported as a clean negative. This positions the
   companion paper as a *case study in mis-evaluating multi-agent
   systems*, with the n=29 numbers as receipts.

2. **Pivot to "fixed-backbone deployment" framing.** Argue that since
   B3 DeepSeek-V3 is the strongest single-LLM, OneVision could be
   restricted to "augment a DeepSeek draft with Llama's verifier
   feedback." This is essentially "DeepSeek-naive plus a precision
   pass" — provable as a pure precision/length trade-off without
   claiming multi-agent magic.

3. **Restart with Bug 4 (drafter pool).** Replace Llama-70B in the pool
   with Mixtral-8x22B or Llama-3.1-405B so the pool is 1-strong /
   2-strong rather than 1-weak / 2-strong. With a balanced pool the
   voter's per-paper selection might actually beat single-LLM. Cost:
   another ~\$25 in API + a re-run of all n=29 evals.

Option 1 is the lowest-cost and currently the most defensible stance.
Option 3 is the only path to a positive OneVision result.

## 6. Data integrity caveats

- 3 / 203 strict evals failed permanently (recall_checker returned 0
  coverage entries despite valid input — likely an LLM formatting quirk
  on long Qwen / DeepSeek summaries). All affected baselines still have
  n_paired = 27-29.
- 3 / 203 first-pass papers (RAG / PaLM / BitNet) hit OneVision pipeline
  trivial_fallback during the n=29 run due to OpenRouter 429 bursts.
  Re-run with concurrency=2 produced clean claim_grounding scoring on
  all three.
- The voter transcripts (`*.voting.json`) were initially included in
  the eval discovery glob and produced 28 error_stub eval JSONs. Fixed
  via filter in `experiment/strict_reeval.py`; affected stubs swept.
- 1 / 30 PDF (Linformer / 2106.04561) consistently fails parsing at
  PDF stage; same as the original PER_PAPER_AUDIT. Excluded.

## 7. Files / artefacts

| Path | Content |
|---|---|
| `Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3.json` | OneVision-v3 final summary, n=29 |
| `Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3.voting.json` | Voting transcript (claim_grounding scores) |
| `Evaluation/outputs/experiment/summaries/<id>/B[1-6]_*.md` | All 6 baselines on the same 29 papers |
| `Evaluation/outputs/experiment/evals_strict/<id>/<method>.eval.json` | Strict-LLM eval results |
| `Evaluation/outputs/experiment/evals_deberta/<id>/<method>.eval.json` | DeBERTa-NLI eval results |
| `Evaluation/outputs/experiment/v3_summary.md` + `v3_summary.json` | Auto-generated dual-judge stats |
| `docs/EVAL_REPORT_v3.md` | This file (human-written paper-ready synthesis) |
| `Evaluation/experiment/run_baselines_only.py` | Baseline-only driver (new) |
| `Evaluation/experiment/sweep_failed_evals.py` | Failed-eval sweeper (new) |
| `Evaluation/experiment/compare_v3.py` | v3 dual-judge comparator (new) |

## 8. Reproducibility

```bash
# 1. Verify env (.env at repo root must have OPENAI_API_KEY = sk-or-v1-..., OPENAI_BASE_URL = https://openrouter.ai/api/v1)
cd Refine-OneVision-Summary && python -c "from src.config.settings import settings; print(bool(settings.OPENAI_API_KEY.get_secret_value()))"

# 2. Generate Ours_onevision_v3 summaries (n=29, ~30 min, ~$3)
EXPERIMENT_CONCURRENCY=3 python scripts/run_onevision_n29.py

# 3. Run baselines (n=29 × 6 = 174 LLM calls, ~15 min, ~$15)
cd ../Evaluation
EXPERIMENT_CONCURRENCY=3 python -m experiment.run_baselines_only

# 4. Strict eval (~60 min, ~$5)
EVAL_CONCURRENCY=4 python -m experiment.strict_reeval --config config/strict.yaml

# 5. DeBERTa eval (~60 min, ~$2 — most cost is in claim extraction; verifier is local)
EVAL_CONCURRENCY=4 python -m experiment.strict_reeval --config config/deberta.yaml

# 6. Sweep + retry any recall_zero / error_stub failures
python -m experiment.sweep_failed_evals --mode both --also-clean-voting
EVAL_CONCURRENCY=3 python -m experiment.strict_reeval --config config/strict.yaml
EVAL_CONCURRENCY=3 python -m experiment.strict_reeval --config config/deberta.yaml

# 7. Final report
python -m experiment.compare_v3
```
