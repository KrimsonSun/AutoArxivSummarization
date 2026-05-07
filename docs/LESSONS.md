# LESSONS — non-obvious findings, append-only

**Format**: `symptom → cause → fix → don't`. Every lesson has an ID
(`L1`, `L2`, …) that other docs can reference. Lessons override priors.
**Append only — never edit existing entries**; if a lesson is later
overturned, add a new lesson that references and supersedes it.

---

## L1 — Family homogeneity caps the refiner ceiling

- **Symptom.** v1 Ours pipeline scores indistinguishably from same-family
  Llama baselines (B1, B5: paired CIs cross zero) but is significantly
  beaten by non-Llama baselines (B2 Qwen ΔF1 = −0.20, d = −1.29; B3
  DeepSeek ΔF1 = −0.16, d = −1.09) on n=29 strict-LLM judge.
- **Cause.** The v1 architecture has a **single Llama-3.3-70B refiner**
  as the terminal bottleneck (verifier + retriever + refiner all use
  the same Llama instance). The pipeline's ceiling is therefore Llama's
  per-call ceiling, regardless of how good the 3 drafters are.
- **Fix.** (a) Replace the static refiner with the *winning* draft's
  LLM (winner-as-refiner, OneVision v2, see EXPERIMENTS E10). This
  lifted vs-B6 from +0.106 to +0.177. (b) Or just use a stronger
  backbone for the refiner directly.
- **Don't.** Don't compare a Llama-only pipeline against cross-family
  baselines and conclude "multi-agent debate fails" — the family
  homogeneity is a confound. (See L7 for the framing fix.)

---

## L2 — Architecture mismatch between paper-reported and module-as-built

- **Symptom.** Two architectures live in this repo and they should
  not be conflated:
  - **Paper-reported** (`RefinedSummarization/paper/main.tex` §3):
    `3 drafters → 1 Llama-70B refiner that synthesises 3 drafts into
    1 final` (= synthesis architecture, debate-as-merge).
  - **Module-as-built** (`Refine-OneVision-Summary/`):
    `3 drafters → 3-round Borda voter (anonymous) → 1 winning draft
    → SingleDraftVerifier on full paragraphs → Retriever → augmenting
    refiner` (= selection-then-augment architecture). Optionally
    K=3 iterative + winner-as-refiner via the `iterative.yaml` config.
- **Cause.** The two papers split into a sequence:
  `RefinedSummarization/paper/main.tex` reports the synthesis pipeline
  (the negative-result paper);
  `Refine-OneVision-Summary/paper/main.tex` reports the selection-then-
  augment pipeline (the companion paper). The
  `RefinedSummarization/src/agents/refiner.py` code is the synthesis
  variant; the `Refine-OneVision-Summary/src/agents/refiner.py` code
  is the augmentation variant. They are deliberately separate modules,
  matching the two-paper sequence.
- **Fix.** No fix needed in code — the divergence is intentional.
  But documentation must keep the two pipelines distinct. The
  earlier confusion (which an external user spec described as
  "HANDOFF v4 / 3 parallel refiners + B7 NLI selector") was based
  on a misremembered design that never existed in this repo. There
  is no third architecture to reconcile. Confirmed with user.
- **Don't.** Don't refer to a third "B7 NLI selector" architecture in
  any new doc / paper. Don't reuse `RefinedSummarization/src/...` to
  test selection ideas — write them in `Refine-OneVision-Summary/`.

See `docs/ARCHITECTURES.md` for the side-by-side ASCII diagram of
both architectures.

---

## L3 — Refiner v1 prompt has internal conflict (intersection vs union)

- **Symptom.** The v1 refiner systematically drops draft-only specifics:
  if only 1 of 3 drafts mentions a number/dataset/method-name, the merged
  output omits it. Lesson L5 (DPR case study) is the smoking gun.
- **Cause.** The v1 refiner system prompt
  (`RefinedSummarization/config/prompts.yaml` →
  `refiner.system`, pre-v2) tells the LLM to "merge the **strongest**
  content from all three drafts." The word "strongest" is ambiguous
  between "best supported" (union-leaning) and "most agreed upon"
  (intersection-leaning), and the LLM defaults to the latter. There
  is no second clause anywhere in `prompts.yaml` to clarify this —
  the prompt is genuinely under-specified, and L5 (DPR case study)
  is direct evidence that the LLM picks the intersection reading.
- **Fix.** v2 refiner prompt is rewritten to lead with `CORE PRINCIPLE —
  UNION, NOT INTERSECTION`, plus three anti-pattern examples
  ("28.4 BLEU → state-of-the-art"; "drop method component"; "smoothing
  three claims into one"), plus a per-field `ALWAYS keep` table. This
  is the "v2 prompt" used in the n=6 sub-experiment and in the
  OneVision pipeline's drafter prompt template.
- **Don't.** Don't assume "merge strongest" is intuitively
  union-biased. Open-source LLMs read it as intersection. If you ever
  write a "merge" or "synthesise" prompt for an LLM, give it a
  per-field ALWAYS-keep rule explicitly.

---

## L4 — Verifier saturates issue cap; refiner rubber-stamps

- **Symptom (NUMBERS UNVERIFIED, recompute next session — see EXPERIMENTS E25).**
  Across the n=29 v1 sample, the verifier reportedly raises issues at
  mean ≈ 12.0 / paper (= the cap of 12), and the refiner reportedly
  self-reports `issues_addressed = 12.0 of 12.0 raised` on every paper.
  Yet paper-side recall remains 0.24 — the refiner's claimed "I
  addressed it" is aspirational, not operational.
- **Cause.** Two compounding problems: (a) the v1 verifier IssueType
  enum lacks a `coverage_gap` type, so the verifier cannot positively
  flag "this fact appears in 1 or 2 of 3 drafts and is paper-supported,
  preserve it." Without that signal, the verifier hits its cap with
  generic `unsupported_claim` / `ambiguity` issues. (b) The refiner
  prompt does not require the refiner to track which issues remain
  open; it just lets the LLM self-report.
- **Fix.** v2 adds `IssueType.COVERAGE_GAP` (in
  `RefinedSummarization/src/schemas/issue.py`) and updates the verifier
  prompt to prioritise raising those. Cap-removal ablation has not
  been run; we don't know the natural distribution of issue counts.
- **Don't.** Don't trust `issues_addressed = N of N raised` as a
  pipeline-quality signal — it's almost certainly LLM compliance
  rather than evidence of fix.

[VERIFY → planned as E25] Recompute by reading
`outputs/experiment/<id>/Ours.json` `metadata.issues_raised` and
`metadata.issues_addressed` across n=29. Confirmed by user as
unverified.

---

## L5 — Intersection bias is real (DPR case study)

- **Symptom.** On `2004.04906` (Karpukhin et al., DPR), the v1
  pipeline's refined summary covers 10 % of paper claims while the
  single-Qwen baseline covers 70 %. Both summaries have ~23–24 atomic
  claims (similar length). The deficit is in *which* facts are picked.
- **Cause.** The 3 drafters between them mention every one of the
  paper's specific architectural choices (CLIP image embedding
  dimension d=1024, hard negatives sampled from BM25, etc.); each is
  mentioned by 1 of the 3 drafters. The v1 refiner intersects: it
  drops every fact that didn't reach 2-of-3 consensus.
- **Fix.** v2 prompt + new COVERAGE_GAP issue type (L3, L4); also see
  L1 fix (winner-as-refiner) which sidesteps merging entirely.
- **Don't.** Don't assume a same-length output is a same-coverage
  output. Length parity is necessary, not sufficient — F1 must be
  measured paper-side, not summary-side.

[VERIFY → planned as E26 / status: possibly chat hallucination] The
"Ours F1=0.18 vs B2 F1=0.82" numbers in the user-provided
documentation spec do not match my OneVision n=29 data on
`2004.04906` (Ours_v1 = 0.491, B2 = 0.049, B3 = 0.182). User
acknowledged the spec numbers may have been chat hallucination from
the original drafting session; will recompute the DPR case-study
numbers directly from `RefinedSummarization/paper/stats.json` /
`paper/main.tex` §7 next session before citing them anywhere.

---

## L6 — M4 (schema-rewards-abstraction) is DEBUNKED

- **Symptom.** Original v1 paper draft (early version) hypothesised
  that the structured-output schema (`tldr / core_idea / method /
  experiments / limitations`) biases toward abstract phrasing — call
  this "Mechanism M4."
- **Cause.** Stats don't support it. B5 (Llama-70B + structured
  prompt) vs B1 (Llama-70B + naive prompt) differ by ΔF1 = −0.04 with
  CI crossing zero (paired n=27). If the structured schema rewarded
  abstraction, B5 should systematically *under*perform B1 by a wider
  margin; it doesn't.
- **Fix.** M4 is retracted in the published paper (§7 of
  `RefinedSummarization/paper/main.tex` ends with "We retract the
  structured-schema mechanism we considered initially"). Mechanisms
  M1, M2, M3 stand.
- **Don't.** Don't reintroduce M4 as a candidate cause in any new
  paper draft. Don't justify changes to the structured output schema
  by appealing to abstraction-rewards.

---

## L7 — Negative-result claims must be scoped narrowly

- **Symptom.** Early paper drafts framed the negative result as
  "multi-agent debate (MAD) fails on union-reconstruction tasks."
  This was too wide.
- **Cause.** The evidence supports a much narrower claim:
  - One specific architecture: 3 drafters → single Llama refiner that
    synthesises → 1 final.
  - One specific backbone family: Llama-3.3-70B in the refiner /
    verifier seat.
  - One specific paper distribution: 29 ML papers from 2017–2024
    (skewed toward NLP / vision / RL; few non-CS).
  - Two specific judges: LLM-as-FActScore + DeBERTa-v3-NLI on
    paragraph-retrieval evidence.
- **Fix.** Reframe (current) title direction: the paper claim is
  "Single-Refiner Bottleneck: Why Multi-Agent Debate Fails on
  Long-Form Summarization", scoped to the synthesis architecture +
  Llama refiner. The companion paper (Refine-OneVision-Summary)
  shows that fixing both the architecture (selection-then-augment)
  and the backbone (winner-as-refiner) recovers within-family
  performance, but does not exceed cross-family backbones.
- **Don't.** Don't claim "MAD fails on union tasks" without the
  scoping. Don't extrapolate to consensus-reasoning tasks (the
  literature shows MAD *helps* there). Don't extrapolate to
  non-research-paper domains.

---

## L8 — Architecture-vs-prompt confound is the dominant open issue (overturned by L9)

- **Symptom.** v1→v2 swing in Ours pipeline is +0.123 F1 (n=6 paired).
  But running the same "v2 union prompt" on a single-LLM baseline (B6)
  also lifts +0.05–0.08 F1. So at n=6, the residual architectural
  contribution `Δ(Ours_v2 − B6) = +0.014` n.s. (CI [−0.13, +0.20]).
- **Cause-as-of-PR-2.** With n=6 and a wide CI, we cannot reject
  "architecture has zero benefit on top of a good prompt." The
  conclusion seemed to be that the v1→v2 lift was driven by prompt
  engineering, not architecture.
- **Fix-attempted-in-PR-3.** Wrote the OneVision pipeline (vote-then-
  augment, verifier-on-full-paragraphs) and ran it on n=15, then n=29.
- **Outcome.** L8's pessimistic reading was overturned at n=29:
  `Δ(OneVision − B6) = +0.106` strict / +0.126 deberta, both ★★ sig.
  The architectural contribution exists; the n=6 ablation was just
  underpowered. L9 supersedes / refines L8.
- **Don't.** Don't treat L8 as the final word. Don't cite the +0.014
  ns figure as evidence that architecture is useless on this task —
  it was a small-n underpowered estimate.

---

## L9 — The voter is a Qwen-bias, not a model selector (per-paper audit)

- **Symptom.** `Δ(OneVision_v1 − B6) = +0.106 ★★` looks like an
  architectural win, but a per-paper audit on the n=27 papers where
  both pipelines ran shows: OneVision (best of v1 / v2) **wins** on
  only 7 / 27 papers, **ties** on 3, and **loses** on 17. Voter
  agreement with the actually-strongest baseline per paper: 14 / 27 =
  52 % (no better than always picking Qwen).
- **Cause.** Stage-2 Borda voter picks Qwen on 26 / 28 papers (~93 %).
  The remaining 7 % of "Llama wins" cases are usually defensive
  fallbacks (one drafter failed, voter has only 2 ballots). DeepSeek
  *never* wins voting. So the OneVision pipeline is, at the level of
  base draft, ≈ "always use Qwen + Llama-augmenter post-process."
  The augmenter then degrades the Qwen draft slightly (paired
  decomposition: ΔP ≈ +0.05, ΔR ≈ +0.10 vs B6, but vs B2 = ΔP ≈
  −0.005, ΔR ≈ −0.09). Net "+0.106 vs B6" decomposes as ~+0.16 from
  base-draft swap (Llama→Qwen) minus ~0.06 from augmenter degradation.
- **Fix.** None implemented yet. The honest reading is that OneVision
  is doing static Qwen-selection masquerading as multi-agent debate.
  A real fix would require: (a) calibrated voter that varies by paper
  (e.g., per-domain backbone selection), or (b) admit OneVision == B2
  with extra steps and sell it as a paper about *fixed-backbone*
  pipelines only.
- **Don't.** Don't write OneVision as "multi-agent debate works after
  architectural fix" without disclosing the voter-bias finding. Don't
  claim "+0.15 over B6" as architectural without naming that ~+0.16
  of it is the model-selection effect.

[VERIFY → planned as E27] Recompute Δ(B2 − B6) on the same n=29
paired sample (this is the "pure Qwen-vs-Llama backbone swap"
contrast). If Δ(B2 − B6) ≈ +0.16 strict / +0.17 deberta, then
`Δ(OneVision − B6) − Δ(B2 − B6) = (augmenter component)` is the
isolated augmenter effect on the Qwen-base case. Decompose to confirm
the +0.16 / −0.06 framing of L9.

---

*Append new lessons below this line. Format: `## L<N> — <one-line title>`
followed by `symptom / cause / fix / don't` paragraphs. ID monotonically
increases.*
