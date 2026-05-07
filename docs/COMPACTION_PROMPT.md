# COMPACTION_PROMPT

Instructions to follow when running `/compact` on a session in this
project. Read these *before* you summarise. The point is to stop
crucial framing / numbers / decisions from being silently dropped in
the compaction summary.

---

## MUST preserve

These items are load-bearing for the next session and **must** survive
compaction. If you can't keep all of them under the token budget,
preserve them in this priority order and drop other content first.

1. **Numbers from `EXPERIMENTS.json`**: the headline F1, paired CI,
   Cohen's d, and W/L/T counts for any concluded experiment. Specifically:
   - The five n=29 v1 contrasts (E1–E5: vs B1, B2, B3, B4, B5).
   - The OneVision v1 vs B6 contrast and v1 vs B2 contrast (E10, E11, E12).
   - The OneVision v2 vs B6 contrast and v2 vs v1 paired (E13, E14).
   - The voter audit summary (E15: Qwen 26/28, OneVision wins 7/27).
2. **L2 architecture mismatch.** Three different architectures exist:
   the v1 paper's "single Llama refiner that synthesises" (paper §3),
   the lost HANDOFF v4's "3 parallel refiner + B7 NLI selector" (never
   implemented, possibly never recoverable), and my Refine-OneVision-Summary
   "Borda voter + augmenter". These are NOT the same and must not be
   conflated.
3. **L3 refiner-prompt internal conflict.** v1's "merge the strongest
   content" reads as intersection to LLMs by default; v2's
   "PRESERVE the UNION" rewrite is what fixed it.
4. **L9 voter-bias finding.** The OneVision +0.106-vs-B6 contrast
   decomposes into ~+0.16 from "voter picks Qwen base instead of
   Llama base" minus ~0.06 from "augmenter degradation". The
   architectural contribution is largely a static Qwen-selection
   heuristic dressed as multi-agent debate.
5. **L6 M4 retraction.** M4 (schema-rewards-abstraction) was
   debunked: B5 vs B1 = −0.04 ns. Do NOT reintroduce M4 as a
   candidate mechanism.
6. **L7 framing scope.** The negative-result claim is scoped to:
   one architecture (synthesis), one backbone family (Llama),
   29 ML papers, two specific judges. Wider claims ("MAD universally
   fails on union tasks") are unsupported.
7. **Planned but unrun ablations** (EXPERIMENTS.json E19–E24) and
   their expected costs. Especially:
   - E19: re-run the 5 stalled long papers under v2 (with timeout fix).
   - E22: 2x2 prompt × refiner-model ablation (reviewer must-have).
   - E23: 3-seed multi-seed re-run (camera-ready prerequisite).
8. **Paper status.** Both papers locked at PR #4 commit `550c4b7`.
   `RefinedSummarization/paper/main.tex` (negative result) and
   `Refine-OneVision-Summary/paper/main.tex` (companion follow-up)
   stay independent — the user has explicitly chosen not to merge.
9. **arXiv preprint timestamp**. **Unknown / not yet locked**. This
   is a real open decision; do not drop the open-question marker.
10. **K8 wall-clock blowup**. The OneVision v2 run died on 5 long
    papers (FlashAttention / CoT / ReAct / DPO / Mistral-7B). Don't
    re-run v2 on n=29 without first adding `asyncio.wait_for` timeouts
    in `Refine-OneVision-Summary/src/llm_clients/openai_client.py`.

## MAY drop

These items are session noise and can be safely dropped from the
compaction summary.

- The chronology of code-edit-by-code-edit work in this session.
- Bash command output that was just confirming a file was written
  (`wrote: ... bytes`, `tests passed: 25 passed`, etc.).
- The chat-window discussion of how to phrase the abstract before the
  final phrasing was committed.
- Intermediate prompt-engineering drafts of the v2 prompt — only the
  final prompt (now committed in `RefinedSummarization/config/prompts.yaml`
  and `Refine-OneVision-Summary/config/prompts.yaml`) matters.
- The Word-document generation pipelines (`/tmp/paper_outline/*.js`):
  these are throw-away build scripts, not project artefacts.
- Monitor task IDs and timestamps from progress notifications during
  long-running experiments.

## MUST NOT do

Hard rules for what NOT to do during compaction.

1. **Do not** describe M4 (schema-rewards-abstraction) as a viable
   mechanism. It was retracted (L6).
2. **Do not** equate the v1 paper's architecture (single-refiner
   synthesis), the lost HANDOFF v4 design (3-parallel + NLI selector),
   and the OneVision module (Borda voter + augmenter). They are
   distinct.
3. **Do not** drop the `[VERIFY: ...]` markers in `LESSONS.md` /
   `EXPERIMENTS.json` / `HANDOFF.md` — those are intentional
   placeholders for the user to validate next session.
4. **Do not** drop file names: `docs/HANDOFF.md`, `docs/LESSONS.md`,
   `docs/EXPERIMENTS.json`, `docs/KNOWN_ISSUES.md`,
   `docs/PIPELINE_SPEC.md`, `docs/PAPER_PLAN.md`, `CLAUDE.md`,
   `PLAN.md`. New sessions need to find these.
5. **Do not** characterise OneVision v2 as "improvement over v1" without
   the n=15 vs n=29 sample-size caveat (E13 / E14 / L9). The mean
   F1 lifted but paired CI on the overlap crosses zero.
6. **Do not** claim OneVision "beats Qwen" — at best it ties B2 within
   noise. The mean tilt flipped between v1 and v2 but no version's CI
   excludes zero against B2.
7. **Do not** drop the K9 / K10 environment caveats — they trip up
   new contributors.

---

*This file itself is stable; do not append to it. If you find a
compaction rule worth adding, edit this file (don't append) and note
in `docs/HANDOFF.md` that you did.*
