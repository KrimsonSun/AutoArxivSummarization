# ARCHITECTURES — what's actually shipped in this repo

Side-by-side ASCII of the two pipeline architectures (one per paper,
**deliberately separate**). Use this when LESSON L2 / EXPERIMENTS E16
is referenced.

---

## Architecture A — Synthesis (RefinedSummarization, v1 / v2)

The **negative-result paper's** pipeline. `RefinedSummarization/src/`.

```
                                  ┌─────────────────────┐
            ┌──── Llama-3.3-70B ──┤  draft 1            ├──┐
            │                     └─────────────────────┘  │
            │                                              │
PDF ────────┼──── Qwen-2.5-72B  ──┤  draft 2            ├──┼─→ ┌──────────────────────────┐
            │                     └─────────────────────┘  │   │  Llama-3.3-70B verifier  │
            │                     ┌─────────────────────┐  │   │  (sees paragraph SHORT-  │
            └──── DeepSeek-V3  ──┤  draft 3            ├──┘   │  SUMMARIES, not full)    │
                                  └─────────────────────┘      └────────────┬─────────────┘
                                                                            │
                                                                  up to 12 issues
                                                                            │
                                                                            ▼
                                                              ┌────────────────────────┐
                                                              │  Llama-3.3-70B retriever│
                                                              │  (per-issue, BM25 +     │
                                                              │  short-summaries)       │
                                                              └────────────┬───────────┘
                                                                            │
                                                                            ▼
              3 drafts + 12 issues + evidence  ─→  ┌────────────────────────────────────┐
                                                    │  Llama-3.3-70B refiner             │
                                                    │  v1 prompt: "merge the strongest"  │
                                                    │  v2 prompt: "PRESERVE THE UNION"   │
                                                    │  Output: 1 FinalSummary            │
                                                    └────────────────────────────────────┘
```

Key properties:
- 3-LLM heterogeneous drafting; **single Llama-70B for all post-draft
  stages** (verifier + retriever + refiner). This is the
  family-homogeneity bottleneck (Lesson L1).
- Verifier sees paragraph **short-summaries** (a Stage-0b artefact);
  loses the very specifics it's supposed to flag (Lesson L4).
- Refiner **synthesises 3 drafts into 1** — debate-as-merge.
  Vulnerable to L3 (intersection bias) and L5 (DPR case-study
  evidence).

## Architecture B — Selection-then-augment (Refine-OneVision-Summary, v1 / v2)

The **companion paper's** pipeline. `Refine-OneVision-Summary/src/`.

```
                                  ┌─────────────────────┐
            ┌──── Llama-3.3-70B ──┤  draft 1            ├──┐
            │                     └─────────────────────┘  │
            │                                              │
PDF ────────┼──── Qwen-2.5-72B  ──┤  draft 2            ├──┤
            │                     └─────────────────────┘  │
            │                     ┌─────────────────────┐  │
            └──── DeepSeek-V3  ──┤  draft 3            ├──┘
                                  └─────────────────────┘
                                                            │
                                                            ▼
                                       ┌──────────────────────────────────────┐
                                       │  GameTheoryVoter                     │
                                       │  3-round, anonymous draft labels,    │
                                       │  Borda count over 3 voters × 3 rounds│
                                       │  (the voters are the SAME 3 LLMs)    │
                                       └────────────────────┬─────────────────┘
                                                            │
                                          1 winning draft (Qwen ~93 %)
                                                            │
                                                            ▼
                                       ┌──────────────────────────────────────┐
                                       │  SingleDraftVerifier (Llama-70B)     │
                                       │  ★ sees FULL paragraph TEXT ★        │
                                       │  emits up to 12 issues               │
                                       └────────────────────┬─────────────────┘
                                                            │
                                                            ▼
                                       ┌──────────────────────────────────────┐
                                       │  Per-issue Retriever (Llama-70B)     │
                                       └────────────────────┬─────────────────┘
                                                            │
                                                            ▼
                  ┌───────── single winning draft + issues + evidence ─────────┐
                  │                                                            │
                  │ Refiner agent:                                             │
                  │   v1 (default.yaml): static Llama-70B refiner; K=1 round   │
                  │   v2 (iterative.yaml): WINNING agent's LLM client; K=3     │
                  │   prompt: "augment, do not rewrite; insert verifier-       │
                  │            flagged missing facts"                          │
                  │ Output: FinalSummary (≤ 1000 words enforced post-hoc)      │
                  └────────────────────────────────────────────────────────────┘
```

Key properties:
- Voter is the consensus-reasoning sub-task (debate is empirically
  good at this).
- Augmenter is the union-reconstruction sub-task (debate failed at
  this in Architecture A; here it's avoided — the augmenter has
  exactly one source draft and a list of paper-grounded
  augmentations, no "merge").
- Verifier reads **full paragraphs** (the L4 fix); sees what the v1
  verifier was missing.
- v2 with `use_winner_as_refiner=true` ensures the winning draft is
  edited by its own producer (avoids L1 family-homogeneity bottleneck
  on the augmenter step).

## What does NOT exist (don't go looking for it)

A "B7 NLI selector" architecture has been mentioned in earlier chat
context but **does not exist in any branch / worktree of this repo**.
It was a misremembered design. If you want a real NLI-based selector,
implement it from scratch — see EXPERIMENTS E20 for the proposed
sketch (DeBERTa-v3-base entailment scores aggregated per draft;
Borda voter swapped out for `src/agents/nli_selector.py`).
