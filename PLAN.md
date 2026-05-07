# PLAN — high-level project roadmap

This file is intentionally short. It only contains things that change
on a project-stage-level (not per-experiment, not per-session).
Per-experiment status lives in `docs/EXPERIMENTS.json`. Open
implementation questions live in `docs/HANDOFF.md` Part B.

For full documentation contract, see `docs/HANDOFF.md` Part A or
`CLAUDE.md`.

---

## Current stage

**Phase 3: Two-paper sequence drafted; locked at PR #4 commit `550c4b7`;
ablation roadmap planned but unrun.**

The two papers stay independent (decided in this documentation session):

- `RefinedSummarization/paper/main.tex` — *negative-result paper*.
  Self-contained: v1 multi-agent debate loses to single-LLM baselines
  on n=29; diagnoses the synthesis-refiner bottleneck. Locked.
- `Refine-OneVision-Summary/paper/main.tex` — *companion follow-up
  paper*. Vote-then-augment redesign; recovers a within-family
  architectural contribution but does not exceed cross-family
  single-LLM baselines. Locked at PR #4. Voter-bias finding
  (`docs/LESSONS.md` L9) was discovered AFTER the paper was last
  compiled; whether to incorporate it into the published companion
  is `docs/HANDOFF.md` Part B Open Question 1.

## Research thesis (in priority order, what each paper claims)

1. **Negative paper.** A specific multi-agent debate architecture
   (3 drafters → single Llama-70B refiner that synthesises into 1
   final) underperforms single-LLM baselines on long-form scientific
   summarisation. Strong evidence at n=29 paired (d = −1.29 vs B2
   Qwen-72B-naive). Diagnosed mechanisms: refiner intersects rather
   than unions (M1), verifier saturates issue-cap and refiner
   rubber-stamps (M2), no paper-side awareness in the pipeline (M3).
   M4 (schema-rewards-abstraction) was tested and retracted.
2. **Companion paper.** Replacing the merging refiner with a
   selection-then-augment architecture (vote-then-augment, with the
   verifier reading full paragraph text instead of paragraph
   short-summaries) yields +0.106 F1 strict / +0.126 deberta over
   the same-prompt single-LLM control (B6). The architectural
   contribution is real within-family but does not exceed
   cross-family single-LLM baselines (B2 Qwen, B3 DeepSeek both
   tied within statistical noise).

## Submission targets / timeline

[Decision needed: ACL 2026 Findings, EMNLP 2026 Findings,
NeurIPS 2026 negative-results workshop, or arXiv-only for now?]

[Decision needed: lock priority by submitting either paper to arXiv
NOW, vs wait for the planned ablations (E19–E24) before timestamping?
The negative paper is fully locked; the companion has open items.]

## Next decision (highest priority for next session)

**Which planned ablation to run first?** Options in
`docs/EXPERIMENTS.json`:

- **E19** Re-run 5 stalled long papers under v2 with timeout fix.
  Cost ~$12, ~90 min. Fixes the most concrete data hole.
- **E22** 2×2 prompt × refiner-backbone ablation (n=29). Cost ~$30,
  ~3 h. Reviewer-must-have for paper revision.
- **E23** 3-seed re-run on locked pipelines. Cost ~$90, ~4 h.
  Camera-ready prerequisite.
- **E20** B7 NLI selector implementation. Blocked on resolving
  L2 architecture mismatch (clarify HANDOFF v4 design with user
  first).

[Decision needed: E19 first (cheap, closes data hole) vs E22 first
(more reviewer-impact) vs E20 first (most novel architectural test).]

## Out of scope for this stage

- Adding new task domains beyond ML papers (e.g., legal documents,
  medical case reports). Save for a v3 paper.
- Adding new evaluator judges beyond strict-LLM and DeBERTa-NLI
  (e.g., human eval, GPT-4 judge). Save for camera-ready.
- Replacing OpenRouter with native provider APIs. Operational only.
- Running the iterative-refinement loop with K > 3 rounds. We don't
  even know K=3 helps over K=1 yet (E14: v2 vs v1 paired = +0.010
  ns).

---

*Updates: this file should change at most once per session, and only
when the project stage transitions or a submission decision is made.*
