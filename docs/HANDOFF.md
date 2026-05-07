# HANDOFF — current state of the AutoArxivSummarization project

This file is the entry point for any new Claude Code session on this project.
Read **Part A** to understand the documentation contract; read **Part B** for
the current state of the work; then read whichever of `LESSONS.md` /
`EXPERIMENTS.json` / `KNOWN_ISSUES.md` / `PIPELINE_SPEC.md` / `PAPER_PLAN.md`
is relevant to your task.

---

## Part A — Stable: how this project's documentation works

### A.1 What this project actually is

A **research project + engineering submodule** mixed:

- **Research half (the papers).** Two LaTeX manuscripts live in this repo:
  - `RefinedSummarization/paper/main.tex` — *negative-result paper*. The v1
    multi-agent debate pipeline loses to single-LLM baselines on n=29 arXiv
    papers; diagnoses the failure mechanisms.
  - `Refine-OneVision-Summary/paper/main.tex` — *companion follow-up paper*.
    A redesigned pipeline (vote-then-augment) that recovers a within-family
    architectural contribution but does not exceed cross-family single-LLM
    baselines.
  - **Decision (locked):** both papers stay independent, neither is to be
    merged into the other. The negative paper is a self-contained study;
    the companion is its architectural follow-up.

- **Engineering half.** Three Python modules:
  - `RefinedSummarization/` — v1/v2 pipeline (3-LLM debate + merging
    refiner). Frozen for reproducibility of the negative-result paper.
  - `Refine-OneVision-Summary/` — v3 / OneVision pipeline (vote +
    augmenter; supports K-round refinement and dynamic winner-as-refiner).
    This is where active development should happen.
  - `Evaluation/` — evaluator + experiment harness shared by both
    pipelines (FActScore-style atomic-claim eval + DeBERTa-NLI judge +
    paired-bootstrap stats).

  All three are imported by a TS frontend (the main `AutoArxivSummarization`
  Next.js app) via `python -m src.cli` subprocess; the contract is "stdout
  = JSON only, stderr = logs".

### A.2 Two senses of "experiment" in this project

- `research_baseline` — paired n=29 (or n=15) F1 / 95% CI / Cohen's d /
  W-L-T comparisons that can land in a paper table.
- `engineering_test` — `pytest` unit tests; smoke runs against a single
  PDF; subprocess-vs-TS contract validation.

`docs/EXPERIMENTS.json` mixes both, distinguished by the `category` field.
`docs/LESSONS.md` is overwhelmingly research-diagnoses, not algo-bug
post-mortems, because the project's hard problems are at the methodology
layer, not the implementation layer.

### A.3 The six-document family (this directory)

| File | Lifecycle | Contains | Does NOT contain |
|---|---|---|---|
| `CLAUDE.md` (repo root) | stable, ≤100 lines | working principles + pointers to other docs | plans, lessons, history |
| `PLAN.md` (repo root) | slow-changing | project-stage roadmap, research thesis, submission targets | per-experiment status |
| `docs/HANDOFF.md` (this file) | Part A stable / Part B per-session rewrite | Part A: contract; Part B: current state | permanent lessons (those go in LESSONS) |
| `docs/LESSONS.md` | append-only | non-obvious findings, format `symptom → cause → fix → don't` | session narrative |
| `docs/EXPERIMENTS.json` | append-only, structured | every experiment: hypothesis / config / metrics / conclusion | free-form discussion |
| `docs/KNOWN_ISSUES.md` | append-only | environment / install / config / API / cache gotchas | algorithm or architecture issues |
| `docs/COMPACTION_PROMPT.md` | stable | instructions to follow when running `/compact` | anything else |

Plus two **legacy documents** (preserved verbatim as historical artifacts —
do **not** edit their content, only re-quote from them):

- `docs/PIPELINE_SPEC.md` — *was* `CONTINUATION_HANDOFF.md` at repo root.
  It is **not** a true 13-chapter implementation spec; it is a v1→v2
  continuation handoff written for a fresh Code window during the PR #2
  era. It references an `original HANDOFF.md` that lived in the deleted
  `epic-euclid-d612ef` worktree and is **permanently lost**. Treat
  `PIPELINE_SPEC.md` as a "where we were at PR #2" snapshot, not as a
  current spec for the OneVision module.
- `docs/PAPER_PLAN.md` — *was* `RefinedSummarization/paper/PAPER_HANDOFF.md`.
  It is a peer-review brief written for an external reviewer to critique
  the n=29 v1 negative-result paper. Used as paper-framing reference only;
  do not edit.

Plus two **session artifacts** (created during the documentation pass
in this session):

- `docs/ARCHITECTURES.md` — side-by-side ASCII of the two pipelines
  (`RefinedSummarization` synthesis vs `Refine-OneVision-Summary`
  selection-then-augment). Cited from Lesson L2.
- `docs/PER_PAPER_AUDIT.md` — frozen n=29 outcome table per paper:
  voter winner, OneVision v1 / v2 F1, all baselines, "OV beats best
  baseline?" verdict. Cited from Lesson L9 / EXPERIMENTS E15.

### A.4 Per-session discipline

**At the start of every session:**
- Read this `HANDOFF.md` Part B first.
- Skim `docs/LESSONS.md` for any lesson tag that touches the current task
  (search for `L1`–`L8+`). Lessons override your priors.
- If you are about to run an experiment, search `docs/EXPERIMENTS.json` for
  prior runs of the same hypothesis — do not re-run a `concluded_*`
  experiment without a clear new hypothesis.

**During the session:**
- Anything you discover that future sessions would want to know goes in
  one of the four append-only docs (`LESSONS`, `EXPERIMENTS.json`,
  `KNOWN_ISSUES`, or Part B of this file).
- Do not edit `PIPELINE_SPEC.md` or `PAPER_PLAN.md` — they are frozen
  historical artifacts.
- Do not edit `LESSONS.md` entries that already exist; add new ones
  (`L9`, `L10`, …) for refinements.

**At the end of every session:**
- Rewrite Part B of this file with the new current state.
- Append any new entries to `LESSONS.md`, `EXPERIMENTS.json`,
  `KNOWN_ISSUES.md`.
- Update `PLAN.md` only if the project stage / submission target changed
  (most sessions won't change those).

### A.5 What goes where (decision tree for "I just learned something")

```
Did this come from a paired-CI / metric / benchmark run?
  ├── yes  → docs/EXPERIMENTS.json (with category, n, metrics, conclusion)
  └── no   → was it a non-obvious finding I want future me not to forget?
              ├── yes → docs/LESSONS.md (symptom→cause→fix→don't)
              └── no  → was it environment / install / API / cache?
                        ├── yes → docs/KNOWN_ISSUES.md
                        └── no  → docs/HANDOFF.md Part B (open questions)
```

---

## Part B — Current state (rewritten 2026-05-07; PR #4 commit `550c4b7`)

### B.1 Where the experiments stand

**v1 RefinedSummarization (negative-result paper, n=29, single seed=42):**

The paper at `RefinedSummarization/paper/main.tex` reports a clean negative
result. v1 Ours pipeline (3-LLM debate + Llama-70B verifier on paragraph
short-summaries + Llama-70B refiner that "merges the strongest content")
loses to single-LLM baselines:

| Baseline | ΔF1 (Ours − bl) | 95 % CI | Cohen's d | sig |
|---|---:|---|---:|:--:|
| B1 Llama-70B-naive | −0.05 | [−0.11, +0.01] | −0.30 | ns |
| **B2 Qwen-72B-naive** | **−0.20** | **[−0.25, −0.14]** | **−1.29** | ★★ |
| B3 DeepSeek-V3-naive | −0.16 | [−0.21, −0.10] | −1.09 | ★★ |
| B4 Llama-8B-naive | −0.05 | [−0.10, −0.01] | −0.43 | ★ small |
| B5 Llama-70B-structured | −0.04 | [−0.08, +0.01] | −0.27 | ns |

(Strict-LLM judge, n=29 paired bootstrap, 10000 resamples, paired n=27–28
varies per baseline due to recall-checker truncation. DeBERTa-NLI judge
agrees on the ranking; absolute numbers slightly different.)

Diagnosis (paper §7): the deficit is paper-side recall (Ours covers
~24 % of paper claims vs B2 ~42 %). Mechanisms M1 (refiner intersects)
and M2 (verifier saturates issue cap, refiner rubber-stamps issues) are
supported. Mechanism M4 (schema rewards abstraction) was retracted —
B5 vs B1 = −0.04 ns, see Lesson L6.

**v1 / v2 prompt-only ablation on n=6 sub-experiment:**
- v2 prompt (union-bias) lifts Ours by ΔF1 = +0.123 paired (strict, CI
  [+0.034, +0.217], W/L/T 5/1/0).
- 2×2 ablation (B1 / B6 Llama-v2-prompt / Ours_v1 / Ours_v2): residual
  architecture-vs-prompt contribution Δ(Ours_v2 − B6) = +0.014, ns at
  n=6. Originally interpreted as "architecture has zero benefit beyond
  prompt"; **this interpretation was overturned** by the OneVision
  experiment below — see Lesson L8.

**OneVision v1 (Refine-OneVision-Summary, n=29 seed=42):**

`Refine-OneVision-Summary/` implements a redesigned pipeline:

```
3 drafters (Llama-70B, Qwen-72B, DeepSeek-V3)
  → 3-round Borda voter (anonymous draft labels)
  → SingleDraftVerifier on FULL paragraphs (NOT short-summaries)
  → per-issue Retriever
  → SingleDraftRefiner (augment, not merge)
```

Single-pass refinement, static Llama-70B refiner. n=23–26 paired:

| Contrast (Ours_v1 − bl) | Strict ΔF1 | DeBERTa ΔF1 |
|---|---:|---:|
| vs B1 Llama-naive | +0.078 ★★ | +0.079 ★★ |
| vs B2 Qwen-naive | −0.072 ns | −0.044 ns |
| vs B3 DeepSeek-naive | −0.041 ns | +0.009 ns |
| vs B4 Llama-8B-naive | +0.128 ★★ | +0.106 ★★ |
| vs B5 Llama-structured | +0.153 ★★ | +0.131 ★★ |
| **vs B6 Llama-v2-prompt** | **+0.106 ★★** | **+0.126 ★★** |

The B6 contrast is the architecture-vs-prompt control. +0.106 strict
significantly exceeds the n=6 prior (+0.014) — Lesson L8 was overturned;
the architecture **does** have a within-family contribution.

**OneVision v2 (iterative + dynamic winner-as-refiner, n=15–21 paired):**

Adds K=3 rounds of (verify → retrieve → refine) and uses the LLM that
won Stage 2 voting as the refiner (instead of a static Llama-70B
refiner). Killed at 24/29 papers OK + 2 errors + 5 long papers
(FlashAttention / CoT / ReAct / DPO / Mistral-7B) timed out — see
Known Issue K8.

| Contrast (Ours_v2 − bl) | Strict ΔF1 (n=15) | DeBERTa ΔF1 (n=21) |
|---|---:|---:|
| vs B2 Qwen-naive | +0.028 ns | −0.026 ns |
| vs B3 DeepSeek-naive | +0.043 ns | +0.036 ns |
| **vs B6** | **+0.177 ★★** | **+0.140 ★★** |
| **vs Ours_v1 (paired)** | **+0.010 ns** | **+0.008 ns** |

The B6 contrast widens from v1 to v2 (+0.106 → +0.177); the v2 mean
F1 (0.653 strict) edges past B2 Qwen (0.645). But v2 vs v1 paired is
+0.010 ns — the iterative-refinement variant does **not** statistically
beat single-pass v1 on the overlap. The mean lift includes selection
bias (the 5 stalled papers were long ones where v2 might have helped).

### B.2 The voter-bias finding (most important new diagnosis, this session)

A per-paper audit of the 28 voting transcripts reveals:

| Voter winner | Frequency |
|---|---|
| Qwen | **26 / 28 (93 %)** |
| Llama | 2 / 28 |
| DeepSeek | 0 / 28 |

Per-paper, OneVision (best of v1 / v2) **loses** to the strongest
single-LLM baseline on **17 / 27 papers**, ties on 3, wins on 7.
Voter agrees with the actually-best baseline only **14 / 27 = 52 %** —
basically Qwen-bias rather than per-paper model selection.

Implication: the +0.106 OneVision v1 vs B6 contrast decomposes
roughly as `+0.16 from "voter picks Qwen base instead of Llama base"
minus 0.06 from "Llama augmenter slightly degrades the Qwen draft"`.
The architectural contribution is **largely a fixed model-selection
heuristic**, not multi-agent debate doing something subtle.

**See Lesson L9** (new this session) for the full implication.

### B.3 The architecture-mismatch question (RESOLVED)

User confirmed: **only two architectures exist in this repo**, and
they are deliberately distinct (one per paper):

- **Synthesis (paper-reported, v1 / v2 negative-result paper).**
  `RefinedSummarization/`: 3 drafters → 1 Llama-70B refiner that
  merges the 3 drafts.
- **Selection-then-augment (companion paper).**
  `Refine-OneVision-Summary/`: 3 drafters → 3-round Borda voter
  (anonymous) → 1 winning draft → SingleDraftVerifier on full
  paragraphs → Retriever → augmenting refiner. Optionally K=3
  iterative + winner-as-refiner via `iterative.yaml`.

Earlier confusion (a hypothesised "HANDOFF v4 / B7 NLI selector"
that allegedly designed a third architecture) was a misremembered
artifact — that design does not exist in any branch / worktree.
There is no third architecture to reconcile.

See `docs/PER_PAPER_AUDIT.md` for the per-paper outcome table that
shows how the OneVision pipeline actually behaved across all 28 valid
papers.

### B.4 Refiner-prompt internal conflict (Lesson L3)

The v1 refiner prompt has two contradictory directives:

- "Merges the **strongest** content from all three drafts." (taken to
  mean "most well-supported", which LLMs default to "most agreed
  upon" → intersection-biased)
There is no second clause in `prompts.yaml` to clarify it — the
prompt is genuinely under-specified, and L5 (DPR case study) shows
the LLM picks the intersection reading by default.

In v2 the conflict is resolved by rewriting the entire refiner
prompt to lead with `CORE PRINCIPLE — UNION, NOT INTERSECTION`
plus 3 anti-pattern examples plus a per-field ALWAYS-keep table.

### B.5 What's locked vs what's open

| Item | Status |
|---|---|
| Negative-result paper (`RefinedSummarization/paper/main.tex`) | **Locked**. n=29 numbers, framing, conclusion all written. Any change goes through a new session task. |
| Companion paper (`Refine-OneVision-Summary/paper/main.tex`) | **Locked at PR #4 commit 550c4b7**. n=29 v1 + n=15-21 v2 numbers, "honest framing" abstract, dual-paper sequence with the negative paper. Any further edit (e.g., incorporating the voter-bias finding from B.2) is a separate session task. |
| Both papers as PDFs | Compiled at PR #4 head via `tectonic`. |
| Code: RefinedSummarization (v1 / v2) | Frozen for paper reproducibility. Do not modify. |
| Code: Refine-OneVision-Summary | Active. K-round + winner-as-refiner shipped in commit `ead4fbb`. |
| Evaluation harness | Active. `compare_onevision.py` + `plot_onevision.py` know about both Ours_onevision and Ours_onevision_v2. |
| arXiv preprint timestamp | **Not submitted yet.** User wants the companion paper polished + Overleaf preview before any arXiv submission. The negative-result paper is locked but is awaiting the companion-paper revisions before the two are submitted as a sequence. |

### B.6 Open questions, ranked by importance

1. **Should the voter-bias finding (B.2 / Lesson L9) be incorporated
   into the companion paper?** Currently the companion paper still
   frames the +0.106 vs B6 as "architectural contribution" without
   the model-selection caveat. The voter-bias analysis was done after
   the paper was last compiled, and the per-paper outcome table is
   now saved at `docs/PER_PAPER_AUDIT.md` for reference. [Decision
   needed next session: rewrite companion §6.3 / §7 to include the
   audit table, or treat it as limitation only?]

2. **What to do about the 5 stalled v2 papers (FlashAttention / CoT /
   ReAct / DPO / Mistral-7B).** These are likely the papers where v2
   would have helped most. Re-running with longer wall-clock ceiling
   (`asyncio.wait_for` timeout config) and Qwen rate-limit tolerance
   (smaller concurrency) is EXPERIMENTS E19. Cost: ~$10–15.

3. **Recompute three pending data items** (E25, E26, E27 in
   EXPERIMENTS.json):
   - E25 verifier-saturation numbers (mean issues raised / addressed
     in v1 n=29; needed to validate L4).
   - E26 DPR case-study numbers (Ours vs B2 F1 on `2004.04906`,
     fact-coverage %; needed to validate L5).
   - E27 Δ(B2 − B6) on n=29 paired (= "pure Qwen-vs-Llama backbone
     swap" contrast); needed to decompose L9's +0.106-vs-B6 finding
     into model-swap vs augmenter components.

4. **arXiv preprint to lock priority.** User has decided: not yet.
   Companion paper to be polished + Overleaf preview first, then both
   papers submitted as a sequence.

5. **Multi-seed validation (×3 seeds × n=29).** Currently every
   experiment is single-seed. For a camera-ready submission this is
   the standard reviewer ask. Cost: 3× current generation +
   evaluation cost ≈ ~$60–100. EXPERIMENTS E23.

### B.7 Next-session actionable list (priority-ordered)

1. **Read `docs/PER_PAPER_AUDIT.md`** — the per-paper outcome table
   from this session (saved to disk; references the L9 voter-bias
   finding). Decide on Open Question 1 (incorporate into companion
   paper or not).
2. **Run E25 + E26 + E27 recomputation scripts** (cheap; no LLM cost,
   just reads off cached eval JSONs):
   - E25: mean issues raised / addressed in v1 n=29 (validates L4).
   - E26: DPR case-study numbers from paper §7 / stats.json
     (validates L5; user notes the "0.18 vs 0.82" figure may be a
     chat hallucination).
   - E27: Δ(B2 − B6) on n=29 paired (decomposes L9's +0.106 into
     model-swap vs augmenter components).
3. **Decide ablation priority** for E19 (5-stalled-paper re-run) vs
   E22 (2×2 prompt × refiner-model) vs E23 (multi-seed). PLAN.md
   has the trade-offs.
4. **Polish companion paper for Overleaf preview** before any arXiv
   submission (per user's submission decision in B.5).

---

*End of HANDOFF.md. For lesson IDs, see `docs/LESSONS.md`. For experiment
IDs, see `docs/EXPERIMENTS.json`.*
