# Paper review handoff

> **For**: an independent reviewer (Claude / GPT / other AI agent) being
> asked to give a detailed peer-review-style critique of the paper draft
> at `paper/main.tex`.
>
> **Mission**: identify any methodological, statistical, or framing
> weakness that would cause this paper to be (a) desk-rejected, (b)
> rejected at peer review, or (c) accepted with major-revision. Suggest
> concrete additional experiments / analyses / textual changes.

---

## 0. TL;DR (the briefing in 90 seconds)

This is a **negative-result paper**. Hypothesis going in: a 3-LLM
debate pipeline with retrieval-augmented verification (\textsc{Ours})
should beat single-LLM summarisation baselines on factuality and
coverage of arXiv papers. Hypothesis after running the experiment:
\textsc{Ours} \emph{loses}.

Specifically, on $n\!=\!29$ arXiv papers across NLP / vision / RL /
diffusion, evaluated by two independent judges (LLM-as-judge in
FActScore-style and a fully-decoupled DeBERTa-v3-NLI classifier),
\textsc{Ours} achieves the lowest F1 across all 6 methods:

-  Strict-LLM: \textsc{Ours} F1 $= 0.37$ vs.\ best baseline (B2 Qwen-72B
   single-call naive prompt) $= 0.57$.
-  DeBERTa-NLI: \textsc{Ours} F1 $= 0.33$ vs.\ best baseline $= 0.50$.
-  Both judges agree on the ranking, so it is not LLM-as-judge bias.
-  $\Delta F_1 = -0.20$ vs.\ B2 Qwen has 95\% bootstrap CI
   $[-0.25, -0.14]$ and Cohen's $d = -1.29$ (very large effect),
   but against \emph{within-Llama-family} baselines (B1, B5) the CI
   crosses zero — the gap is not statistically significant.

Diagnostic case studies and the M2 saturation evidence point at the
**refiner** intersecting drafts rather than unioning them: same-length
output, but draft-only specifics get dropped during merge.

The paper's framing pivots on this observation: multi-agent debate
helps **consensus-reasoning** tasks (one truth, agents converge)
because it averages out noise; it hurts **union-reconstruction**
tasks (many facts, agents must aggregate breadth) because it
intersects drafts. The paper proposes this as a task-type taxonomy.

---

## 1. Repo structure

```
AutoArxivSummarization/.claude/worktrees/epic-euclid-d612ef/
├── HANDOFF.md                       ← original spec for the implementation
│                                       (NOT this handoff — that one is
│                                       upstream design doc)
├── RefinedSummarization/
│   ├── src/                         ← the 3-LLM debate pipeline
│   ├── config/
│   │   └── prompts.yaml             ← agent prompts (incl. v2 changes)
│   ├── CHANGELOG_V2.md              ← documented v2 architecture changes
│   └── paper/
│       ├── main.tex                 ← THE PAPER (this is what you review)
│       ├── references.bib           ← bibliography
│       ├── stats.json               ← raw numbers for every claim
│       ├── figures/                 ← 8 figures referenced from main.tex
│       ├── README.md                ← Overleaf upload + revision history
│       └── PAPER_HANDOFF.md         ← this file
└── Evaluation/
    ├── src/                         ← the 3-mode evaluator
    │   ├── nli_verifier.py          ← DeBERTa-v3-NLI verifier
    │   ├── paper_claim_extractor.py ← Step 5 (paper → atomic claims)
    │   └── recall_checker.py        ← Step 6 (paper-claim coverage check)
    ├── config/
    │   ├── default.yaml             ← loose mode
    │   ├── strict.yaml              ← strict-LLM mode
    │   └── deberta.yaml             ← DeBERTa-NLI mode
    ├── experiment/
    │   ├── paper_pool.py            ← 30-arXiv-ID curated pool
    │   ├── baselines.py             ← 5 single-LLM baselines
    │   ├── run.py                   ← end-to-end orchestrator
    │   ├── strict_reeval.py         ← strict-mode re-evaluator
    │   ├── plot.py                  ← per-paper + mean charts
    │   ├── draw_diagrams.py         ← pipeline + results table figures
    │   └── stats.py                 ← bootstrap CI + Cohen's d + cases
    └── outputs/experiment/          ← 522 EvaluationReport JSON files
        ├── papers/                  ← 30 cached PDFs (Linformer 2106.04561 fails)
        ├── summaries/               ← 29 papers × 6 methods = 174 summaries
        ├── paper_claims/            ← 29 cached paper-side atomic-claim sets
        ├── evals/                   ← 174 loose-mode reports
        ├── evals_strict/            ← 174 strict-LLM-mode reports
        ├── evals_deberta/           ← 170 DeBERTa-NLI reports (4 PaLM 2 fallbacks)
        └── plots/                   ← 24 per-paper charts + 3 modes mean + 3 diagrams
```

Two PRs of record:
-  PR #1 (merged): initial implementation of \textsc{RefinedSummarization}
   pipeline + \textsc{Evaluation} loose mode.
-  PR #2 (open):  added strict-LLM + DeBERTa-NLI modes, ran the n=29
   experiment, drafted the paper, plus untested v2 architecture fixes.

---

## 2. The pipeline being evaluated (\textsc{Ours})

3-LLM debate + retrieval-augmented verification + refiner. See
`paper/main.tex` §3 for the full description. In short:

```
PDF
 ├──→ parse (pdfplumber)
 │
 ├──→ 3 drafts in parallel (asyncio.gather)
 │       Llama-3.3-70B  Qwen-2.5-72B  DeepSeek-V3
 │       ↓               ↓             ↓
 │     each produces a structured FinalSummary skeleton
 │     with explicit evidence_refs to paragraph IDs
 │
 ├──→ verifier (1 LLM call on Llama-3.3-70B, strict prompt)
 │       returns ≤ 12 typed issues (factual_error, missing_info, ...)
 │
 ├──→ retriever (per-issue, BM25 over paper paragraphs)
 │       returns top-5 paragraphs as evidence
 │
 └──→ refiner (1 LLM call on Llama-3.3-70B)
          ingests: 3 drafts + issue list + evidence + full paragraphs
          outputs: 1 merged FinalSummary + issues_addressed list
```

All open-weights, all routed through OpenRouter. Total $\sim$30 LLM
calls per paper.

## 3. The evaluator (\textsc{Evaluation})

For every (summary, paper) pair we run a 4-step (loose) or 6-step
(strict) pipeline. See `paper/main.tex` §4 + Figure 1 for the full
diagram.

```
Step 1: Summary → atomic claims          (LLM)
Step 2: BM25 retrieval per claim         (CPU)
Step 3: Verify (claim, evidence) → verdict
        Loose:       LLM lenient prompt
        Strict-LLM:  LLM strict prompt (numeric / named-entity match)
        DeBERTa-NLI: local DeBERTa-v3-base classifier on MPS
Step 4: Aggregate → precision, hallucination

(strict modes only:)
Step 5: Paper → atomic claims            (LLM, cached, shared across 6 methods)
Step 6: For each paper claim, covered?   (LLM, batched once per (paper, summary))
Step 4b: → recall, F1
```

The DeBERTa-NLI verifier is the cross-validation: it was never trained
on outputs from any of our generation models, so its agreement with
strict-LLM rules out same-model self-favouring.

---

## 4. Key results to verify

These are the headline numbers in the paper. All are reproducible from
`Evaluation/outputs/experiment/` and `paper/stats.json`.

### 4.1 Mean F1 across n=29 papers

| Method                | Strict-LLM F1     | DeBERTa-NLI F1    |
|-----------------------|------------------:|------------------:|
| **Ours**              | $0.370 \pm 0.15$  | $0.331 \pm 0.16$  |
| B1 Llama-70B-naive    | $0.418 \pm 0.17$  | $0.370 \pm 0.20$  |
| **B2 Qwen-72B-naive** | **$0.569 \pm 0.18$** | **$0.499 \pm 0.18$** |
| B3 DeepSeek-V3-naive  | $0.531 \pm 0.16$  | $0.459 \pm 0.18$  |
| B4 Llama-8B-naive     | $0.419 \pm 0.16$  | $0.374 \pm 0.16$  |
| B5 Llama-70B-struct   | $0.405 \pm 0.16$  | $0.355 \pm 0.15$  |

### 4.2 Paired-bootstrap CIs (Ours − baseline) on strict-LLM F1

| vs.\ baseline           | $\Delta F_1$ | 95% CI            | Cohen's $d$ | W/L/T (28) |
|-------------------------|-------------:|-------------------|------------:|-----------:|
| B1 Llama-70B-naive      | $-0.05$      | $[-0.11, +0.01]$  | $-0.30$     | 8/16/3     |
| **B2 Qwen-72B-naive**   | $-0.20$      | $[-0.25, -0.14]$  | $-1.29$     | **1/26/1** |
| B3 DeepSeek-V3-naive    | $-0.16$      | $[-0.21, -0.10]$  | $-1.09$     | 4/22/1     |
| B4 Llama-8B-naive       | $-0.05$      | $[-0.10, -0.01]$  | $-0.43$     | 8/13/6     |
| B5 Llama-70B-structured | $-0.04$      | $[-0.08, +0.01]$  | $-0.32$     | 9/17/2     |

Three of five CIs (B1, B4, B5) come close to or cross zero. Only the
non-Llama baselines (B2, B3) yield a statistically clean negative result.

### 4.3 Case studies

Top three papers by largest $F_1(\textsc{Ours}) - F_1(\textsc{B2})$
(most negative gap):

| Paper                      | Ours $F_1$ | B2 $F_1$ | Ours $R$ | B2 $R$ | $|S_\text{Ours}|$ | $|S_\text{B2}|$ |
|----------------------------|-----------:|---------:|---------:|-------:|------------------:|----------------:|
| 2004.04906 DPR             | 0.18       | 0.82     | 0.10     | 0.70   | 23                | 24              |
| 2205.14135 FlashAttention  | 0.37       | 0.78     | 0.225    | 0.65   | 14                | 19              |
| 2204.05862 Constitutional AI| 0.26      | 0.61     | 0.15     | 0.475  | **33**            | 30              |

In all three, \textsc{Ours} writes a comparable or larger number of
atomic claims but covers far fewer paper facts. Constitutional AI is
particularly informative: \textsc{Ours} writes 33 atomic claims (more
than B2's 30) yet covers half as many paper facts.

### 4.4 Saturation evidence (M2)

Across all 29 papers:

```
mean issues raised by verifier:    12.0  (out of max 12 — always saturated)
mean issues_addressed by refiner:  12.0  (always self-reports 100%)
yet mean paper_recall:              0.24  (Ours)
```

This is consistent with rubber-stamp behaviour: the refiner says it
addressed everything, but recall stays low. The current verifier
issue types do not include a coverage-gap signal, so the refiner has
no positive instruction to preserve draft-only specifics.

---

## 5. Statistical hardening already applied

The current paper already includes (after the v2 review-pass):

-  Paired-bootstrap 10k-iteration CIs on F1 differences.
-  Cohen's $d$ effect sizes (computed paired, $\mu(\text{diff})/\sigma(\text{diff})$).
-  Per-paper W/L/T counts at $\pm 0.02$ tolerance.
-  Per-paper scatter plot (`figures/per_paper_scatter.png`).
-  Per-paper diff histogram with bootstrap CI (`figures/diff_distribution.png`).
-  Within-experiment per-paper std-dev as proxy for run-to-run noise.
-  Mechanism M4 retracted because the data does not support it.
-  Reproducibility section with pinned model snapshots, temperatures,
   max\_tokens, and constant paper-claim-cache denominator.
-  iLLMV citation flagged as `[PLACEHOLDER]` to prevent accidental
   anonymity violation.

## 6. Things explicitly NOT done (potential desk-reject vectors)

-  **Single seed.** Experiment ran once with `random.seed(42)`. We
   disclose this in §9 and use within-experiment std-dev as proxy,
   but multi-seed averaging is the right thing to do for camera-ready.
   Estimated cost to do 3 seeds: $\sim$\$30 OpenRouter, $\sim$3 h
   wall-clock.
-  **Atomic claim extractor is the same Llama-70B used in the
   pipeline.** Section 9 (ii) discloses; a definitive control would be
   to use a non-Llama claim extractor.
-  **The v2 architecture fixes (M1 union refiner, M2 coverage\_gap
   issue type) are implemented but UNTESTED.** §7 says so plainly.
   Independent ongoing validation is referenced but not reported.
-  **No human-evaluator agreement study.** Both judges are LLMs (or
   LLM-trained NLI); a human spot-check on $n=20$ verdicts would
   meaningfully strengthen the paper.
-  **No ablation on Ours.** We don't show what each component
   (debate / verifier / RAG / refiner) contributes individually.
   This would isolate which stage is responsible for the regression
   beyond what M1's case studies suggest.

## 7. Things we're worried about (please critique these)

1. **Is the task-type taxonomy convincing?** We assert that
   consensus-reasoning vs.\ union-reconstruction is the right
   distinction, and that multi-agent debate transfers poorly between
   them. The SpecEM paragraph in §2 supports this, but a real reviewer
   might want a more rigorous taxonomy (e.g., a 2$\times$2 grid of
   tasks with empirical results in each cell).

2. **Within-family vs.\ cross-family CI difference.** B1/B5
   (Llama-family) CIs cross zero, but B2/B3 (other families) are
   strongly negative. We frame this as "the failure is non-uniform",
   but a reviewer could argue this just shows our pipeline is
   **uninformative** (i.e., adding two Llama-equivalent agents on top
   of one Llama doesn't help and doesn't hurt — which is itself a
   weak claim about debate's value).

3. **Are the case studies (DPR, FlashAttention, Constitutional AI)
   cherry-picked?** We disclose that they are the top-3-largest-gap
   papers, but a reviewer might ask for the bottom-3 or
   middle-3 to confirm the mechanism is general.

4. **Paper-claim extractor is shared across all 6 methods.** This
   should make the comparison fair, but if the extractor has a
   persona-specific bias (e.g., it extracts more claims from papers
   that match its training distribution), it might systematically
   reward Qwen-style output. We argue this is unlikely because the
   extractor is Llama-70B (same family as our pipeline), so any
   bias should favour Ours, not Qwen. Reviewer may push back.

5. **Title and framing.** Current title leans negative-result. An
   alternate framing (proposed but not adopted) is to centre the
   task-type taxonomy as the positive contribution. Trade-off:
   negative-result framing is clear and bookable for venues that
   solicit them; taxonomy framing is more ambitious but harder to
   sell with $n=29$.

## 8. Specific evaluation prompts for the reviewer

If you (the reviewing agent) are short on time, focus on these:

1. **Statistical**: Do the bootstrap CIs and Cohen's $d$ values
   actually support the conclusions in §5 and §6? In particular,
   does the within-Llama-family null finding undercut the broader
   claim about debate failure?

2. **Causality of M1**: §6 attributes the recall deficit to the
   refiner's "merge strongest" prompt. Is the case-study evidence
   sufficient, or does this need a controlled ablation (run the same
   debate without a refiner, or with multiple refiner prompts)?

3. **Scope of the negative result**: Does the paper overclaim?
   Specifically, is "multi-agent debate fails on union-reconstruction
   tasks" supported by 29 arXiv summarisation papers, or should it be
   "...on this particular instantiation of multi-agent debate, on
   this particular set of arXiv papers, evaluated by these
   particular judges"?

4. **Related-work coverage**: We cite Du et al. 2023, AutoGen,
   Self-Refine, FActScore, SummaC, RAG. Are there must-cite related
   works on summarisation factuality (e.g., HaluEval, FENICE, MENLI)
   or on multi-agent failure modes (e.g., recent NeurIPS work on
   when MAD fails) that we are missing?

5. **Reproducibility**: Given pinned model IDs, single seed, and the
   committed 522 evaluation reports, can you actually re-derive any
   of the numbers in the paper from `paper/stats.json` and the
   committed `Evaluation/outputs/experiment/` directory?

6. **Where would this paper desk-reject?** Best-guess venues:
   ACL Findings, EMNLP Findings, NeurIPS workshops, ICLR
   workshops, ARR. What's the single most likely reason a
   programme committee would refuse to send this out for review?

7. **What's the easiest 1-day experiment that would substantially
   strengthen the paper?** Ranked priority:
   - 3-seed re-run (~3 h, ~\$30): converts single-seed disclosure
     into proper variance estimates.
   - Ablation: run \textsc{Ours} without the refiner (just take
     the union of the 3 drafts naively) (~30 min, ~\$3): isolates
     whether the refiner is the problem.
   - Run v2 prompts (already implemented) and report whether F1
     lifts from 0.37 to ≥ 0.50: validates the proposed fix.
   - Human spot-check on $n=20$ DeBERTa verdicts (~1 day,
     no compute): grounds the negative result against human judgement.

   Which of these is most worth doing first?

---

## 9. How to inspect the actual data

Everything in the paper is derivable from this directory. Useful
entry points:

```bash
# Paper itself (compiles standalone with pdfLaTeX)
RefinedSummarization/paper/main.tex

# Every number in the paper, in JSON
cat RefinedSummarization/paper/stats.json | jq

# The 522 raw evaluation reports (4 KB each, structured Pydantic)
ls Evaluation/outputs/experiment/evals_strict/*/   # 174 files
ls Evaluation/outputs/experiment/evals_deberta/*/  # 170 files

# Re-derive any single statistic
cd Evaluation && .venv/bin/python -m experiment.stats

# View a specific case-study summary side-by-side
cat Evaluation/outputs/experiment/summaries/2004.04906/Ours.json | jq
cat Evaluation/outputs/experiment/summaries/2004.04906/B2_qwen_naive.md
```

Pull-request that contains all of this: PR #2 in
`KrimsonSun/AutoArxivSummarization`, branch `claude/epic-euclid-d612ef`.

---

## 10. What we want back from you

A peer-review-style critique in any format you prefer. We are
particularly interested in:

-  **Killer holes**: things that would cause desk-reject at a top venue.
-  **Missed experiments**: ablations or controls you'd require.
-  **Framing alternatives**: better story arcs we haven't considered.
-  **Citation gaps**: must-cite related work we missed.
-  **Statistical mistakes**: improper bootstrap, wrong $d$ formula,
   etc.

If you have time, please also rate this paper on a 4-point scale per
ACL conventions (strong reject / weak reject / borderline / weak
accept / strong accept) and explain.

Thank you.
