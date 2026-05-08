# Continuation Handoff — for the next Code window

> This document is a self-contained briefing for a fresh Claude Code
> session that picks up the work in PR #2 of
> `KrimsonSun/AutoArxivSummarization`. Read it through, run the
> sanity check in §6, then pick up at §3 ("the open scientific
> question").
>
> **You should NOT need to read the prior conversation.** Everything
> required to continue is written into the repo + this handoff +
> `paper/PAPER_HANDOFF.md`.

---

## 1. State of the repo (where we are)

Branch: `claude/epic-euclid-d612ef`  
PRs of record:
-  **PR #1** (merged): initial implementation — `RefinedSummarization/`
   (3-LLM debate pipeline) and `Evaluation/` loose mode.
-  **PR #2** (open): added strict-LLM + DeBERTa-NLI evaluation modes,
   ran the n=29 benchmark, drafted the paper, implemented v2
   architecture fixes, and ran a 7-paper v2 small-scale validation
   that produced a positive result.

Working directory:

```
AutoArxivSummarization/.claude/worktrees/epic-euclid-d612ef/
├── HANDOFF.md                       ← original spec for the implementation
├── CONTINUATION_HANDOFF.md          ← THIS FILE
├── RefinedSummarization/
│   ├── src/                         ← 3-LLM debate pipeline
│   ├── config/prompts.yaml          ← agent prompts (v2 already applied)
│   ├── CHANGELOG_V2.md
│   └── paper/                       ← LaTeX paper draft
│       ├── main.tex
│       ├── stats.json               ← every number behind the paper
│       ├── PAPER_HANDOFF.md         ← briefing for the paper-review chat
│       └── figures/
└── Evaluation/
    ├── src/                         ← 4-step evaluator
    ├── config/{default,strict,deberta}.yaml
    ├── experiment/
    │   ├── paper_pool.py            ← 30 arXiv IDs, seed-fixed sampling
    │   ├── baselines.py             ← 6 single-LLM baselines (B1-B6)
    │   ├── run.py                   ← end-to-end orchestrator
    │   ├── strict_reeval.py         ← strict-mode re-evaluator
    │   ├── run_v2_test.py           ← 7-paper v2 small-scale validation
    │   ├── compare_v1_v2.py         ← v1 vs v2 paired-bootstrap stats
    │   ├── stats.py                 ← n=29 paired-bootstrap CI + Cohen's d
    │   ├── plot.py                  ← per-paper + mean charts
    │   └── draw_diagrams.py         ← pipeline + results diagrams
    └── outputs/experiment/          ← 522 EvaluationReport JSON files
        ├── papers/                  ← 30 cached PDFs
        ├── summaries/               ← 7 v2 + 29×6 v1 summaries
        ├── paper_claims/            ← cached paper-claim sets per paper
        ├── evals/                   ← loose-mode reports
        ├── evals_strict/            ← strict-LLM reports (29×6 + 7 v2)
        └── evals_deberta/           ← DeBERTa-NLI reports (similar)
```

OpenRouter spend so far: $\sim$\$15. Budget remaining at handoff: depends on
the user's account, but ~$15-25 is realistic for the next round of
experiments described in §4.

---

## 2. What the previous chat accomplished

In rough order:

1. Implemented the 3-LLM debate pipeline (\textsc{RefinedSummarization})
   and a 4-step evaluator (\textsc{Evaluation}) per `HANDOFF.md` (PR #1).
2. Extended the evaluator with two stricter modes:
   -  `strict-LLM`: tightened verifier prompt + paper-side recall + F1
   -  `DeBERTa-NLI`: replaces the LLM-as-judge step with a local
      DeBERTa-v3-base-mnli-fever-anli classifier (decoupled from the
      generation stack to rule out same-model self-favouring)
3. Built a 30-paper benchmark + 5 single-LLM baselines (B1-B5) and ran
   the full $n=29$ experiment under all 3 modes (522 evaluation reports).
4. Found that \textsc{Ours} ranks **last** on F1 across both judges:
   - Strict-LLM: \textsc{Ours} 0.37 vs.\ B2 Qwen-72B-naive 0.57 (best).
   - DeBERTa: \textsc{Ours} 0.33 vs.\ B2 0.50.
   - Δ vs.\ B2 = $-0.20$, 95\% CI $[-0.25, -0.14]$, Cohen's $d = -1.29$.
5. Drafted a paper (`paper/main.tex`) framing this as a negative
   result with task-type taxonomy: multi-agent debate works for
   *consensus-reasoning* tasks but fails for
   *union-reconstruction* tasks.
6. Diagnosed four mechanisms; M4 (schema rewards abstraction) was
   retracted because B5 vs.\ B1 are statistically tied.
7. Implemented v2 architecture fixes (still in
   `RefinedSummarization/config/prompts.yaml` right now):
   -  **Refiner prompt** rewritten to bias toward UNION (preserve
      every specific fact from any draft; never silently drop numbers
      / dataset names / method components).
   -  **New IssueType.COVERAGE\_GAP** + verifier instructions to flag
      facts present in 1-2 of 3 drafts.
8. Ran a 7-paper v2 small-scale validation (§3 below).

---

## 3. The open scientific question

The 7-paper v2 validation (using the SAME seed-42 sample as the n=29
benchmark; data in `evals_strict/<id>/Ours_v2.eval.json` and
`evals_deberta/<id>/Ours_v2.eval.json`) shows v2 substantively
improves over v1:

| Mode | Mean ΔF1 (v2 - v1) | 95% CI | Cohen's $d$ | W/L/T (n=6) |
|---|---:|---|---:|---|
| Strict-LLM | $+0.123$ | $[+0.034, +0.217]$ | $+0.97$ | 5/1/0 |
| DeBERTa-NLI | $+0.108$ | $[+0.050, +0.159]$ | $+1.49$ | 5/0/1 |

Gap to B2 Qwen-72B-naive (the strongest baseline) closed:

| Mode | v1 ΔF1(Ours - B2) | v2 ΔF1(Ours_v2 - B2) | v2 95% CI |
|---|---:|---:|---|
| Strict-LLM | $-0.12$ | $-0.00$ | $[-0.15, +0.15]$ |
| DeBERTa | $-0.08$ | $+0.03$ | $[-0.07, +0.12]$ |

(One paper, PaLM 2 / 2305.10403, was excluded because v2 summaries
are longer and the recall-checker LLM call truncated. See §5 known
issues.)

### The new question

**v2 vs.\ v1 cannot distinguish two hypotheses:**

(a) **Architectural**: the 3-LLM debate provides genuine information
    that the v1 refiner was wasting; v2 prompt unlocks it. Single-LLM
    baselines cannot match v2 even with the same prompt-engineering
    advantages, because they don't have 3 drafts to union over.

(b) **Prompt engineering**: any decent prompt-engineering pass would
    have raised F1 by roughly the same amount; the multi-agent
    architecture adds no value beyond what good prompting alone can
    achieve.

This is **the** disambiguation needed before submitting the paper.
Without it, a reviewer can correctly say "you didn't isolate prompt
engineering as a confound."

### The 2×2 ablation that answers it

|                     | naive prompt | v2-style union prompt |
|---------------------|---|---|
| **single LLM** (1 call) | B1 / B5 (existing) | **B6 (NEW)** |
| **3-LLM debate** | v1 \textsc{Ours} (existing) | v2 \textsc{Ours\_v2} (existing) |

If $F_1(\text{B6}) \approx F_1(\textsc{Ours\_v2})$ → hypothesis (b)
→ multi-agent is decoration, just rewrite the prompt.

If $F_1(\text{B6}) \ll F_1(\textsc{Ours\_v2})$ → hypothesis (a) →
the 3-LLM debate genuinely helps when the merge step is told to
union rather than intersect.

A natural intermediate outcome: $F_1(\text{B6})$ closes most but not
all of the v1→v2 gap, in which case the paper's contribution becomes
"multi-agent debate has a small but real benefit on top of good
prompting." That's also publishable and arguably more honest.

---

## 4. Your task

### 4.1 Run the 2×2 ablation

B6 is already scaffolded as a 6th baseline. Look at:

```
Evaluation/experiment/baselines.py
```

You'll see B6\_llama\_v2prompt with `prompt_kind="v2_inspired"` and a
\_V2\_INSPIRED\_SYSTEM prompt that mirrors the union-bias / specificity
directives from the v2 refiner prompt, adapted for a single-call
no-debate setting (no "merge from 3 drafts" wording).

Steps to run:

```bash
cd Evaluation
.venv/bin/python -m pytest tests/ -q     # sanity: 16 passed
# 1. Generate B6 summaries for the same 7 papers as the v2 small-scale test
EXPERIMENT_CONCURRENCY=4 .venv/bin/python -m experiment.run 7 42 \
    > outputs/experiment/run_b6.log 2>&1
# (this re-runs the orchestrator — B1-B5 + Ours all cache-hit and skip;
#  only B6 is new. Note: experiment.run won't generate Ours_v2 because
#  it's not in the standard pipeline; v2 was generated by run_v2_test.)

# 2. Evaluate B6 in strict + deberta modes (paper claims cached)
EVAL_CONCURRENCY=4 .venv/bin/python -m experiment.strict_reeval \
    --config config/strict.yaml \
    --papers 2204.06125 2104.08691 1706.03762 2112.10752 2204.02311 \
             2305.10403 1707.06347 \
    >> outputs/experiment/run_b6.log 2>&1

EVAL_CONCURRENCY=4 .venv/bin/python -m experiment.strict_reeval \
    --config config/deberta.yaml \
    --papers 2204.06125 2104.08691 1706.03762 2112.10752 2204.02311 \
             2305.10403 1707.06347 \
    >> outputs/experiment/run_b6.log 2>&1
```

Cost: $\sim$\$2 OpenRouter, $\sim$10 minutes wall-clock.

### 4.2 Analyse the 2×2

The existing `experiment/compare_v1_v2.py` is set up for v1 vs v2
on Ours. Extend it (or write `experiment/compare_2x2.py`) to compare:

- $F_1(\text{B1\_naive})$
- $F_1(\text{B5\_structured})$
- $F_1(\text{B6\_v2prompt})$  ← new
- $F_1(\textsc{Ours v1})$
- $F_1(\textsc{Ours v2})$

For each pair, compute paired bootstrap CI on F1 differences, Cohen's
$d$, and W/L/T counts.

The headline question to answer:

```
F1(B6) - F1(B1)  =  ?       # effect of v2 prompt on single LLM
F1(Ours_v2) - F1(B6)  =  ?   # effect of multi-agent debate ON TOP of v2 prompt
F1(Ours_v2) - F1(Ours_v1)  =  ?   # effect of v2 prompt on multi-agent (we know this: ~+0.12)
F1(Ours_v1) - F1(B1)  =  ?   # effect of multi-agent debate WITHOUT prompt fix (we know this: ~−0.05, ns)
```

Interaction effect = the third minus the fourth. If the interaction
is positive and large, the v2 prompt + multi-agent combo is
synergistic. If interaction ≈ 0, they're independent (additive
prompt-engineering gain only).

### 4.3 Update the paper

Once §4.2 is in, update `paper/main.tex` Section 7 (Toward a
Coverage-Aware Pipeline) from "v2 fixes implemented but untested" to
"v2 fixes validated; the gain decomposes as X% prompt engineering and
Y% multi-agent architecture." Make one new figure showing the 2×2.

If the result is bleak (multi-agent contributes nothing on top of
prompt), reframe Section 8 (Conclusion) accordingly: the negative
result is even sharper.

If the result is positive (multi-agent contributes meaningfully),
update the abstract to say "we identify the failure mechanism, propose
a fix, and validate that the architecture provides $\Delta F_1 = ?$
on top of better prompting alone."

### 4.4 Don't forget

- **PaLM 2 (2305.10403) recall-checker truncation.** The v2 summary
  is long enough that even with `max_tokens=16384` in the recall
  checker, the LLM output JSON gets cut off and the defensive
  fallback fires. Look at `Evaluation/src/recall_checker.py`. The
  proper fix is to split the 40 paper claims into batches of $\le$20
  and call twice. This is a 30-line code change, but you should also
  rerun PaLM 2 strict + deberta after the fix (otherwise you'll have
  6/7 papers instead of 7/7 in the v1-vs-v2 table, and the same
  problem will recur on the eventual full-29 v2 run).

- **Single seed.** All experiments run with `random.seed(42)` and
  drafter `T=0.7`. For camera-ready, multi-seed averaging
  (3 seeds × ~$30 each) would convert the §9 single-seed disclosure
  from "we acknowledge this" to "robustness to seed noise verified."
  Optional but recommended.

---

## 5. Known issues

1. **PaLM 2 (2305.10403) recall checker truncation.** See §4.4. The
   recall checker max\_tokens is 16k but PaLM 2 has 40 paper claims and
   v2 summaries are denser, so the JSON output gets cut and triggers
   the defensive all-NotCovered fallback (resulting in F1=0). Fix by
   batching the recall check.

2. **The 24/29 fully-complete papers** in `evals_strict/` had a recall
   check that succeeded; 5/29 had at least one method's recall check
   fall back. They are: 2305.10403 (PaLM 2 — same root cause),
   1707.06347 (PPO), 2204.05862 (Constitutional AI), 2305.10601
   (ToT), 2305.14233 (RLAIF). These all share the "long paper, many
   paper claims" property.

3. **`Ours_v2.json`** files exist only for the 7-paper v2 test. To
   run v2 on all 29, you'd need to either (a) backup the existing
   29 v1 `Ours.json`, then run `experiment.run 29 42` again (config
   prompts are already v2, so this generates v2 outputs and overwrites
   v1) — destructive; or (b) modify `experiment/run.py` to take a
   `--method-name` arg that controls the output filename. Option (b)
   is cleaner.

4. **`paper/main.tex` Section 7** still says v2 is "implemented but
   not yet validated"; it needs a one-paragraph update once the 2×2
   numbers come in.

5. **iLLMV citation in `paper/references.bib` is a placeholder.**
   Find the actual IEEE BigData 2025 reference before submission.

6. **OpenRouter model pinning.** The exact snapshots in use are
   declared in `paper/main.tex` §5 reproducibility section. If those
   snapshots get rotated by OpenRouter, behaviour may drift.

---

## 6. Sanity check before continuing

```bash
cd /Users/yijunsun/Documents/Git/AutoArxivSummarization/.claude/worktrees/epic-euclid-d612ef

# 1. Verify code compiles
cd RefinedSummarization && .venv/bin/python -m pytest tests/ -q
# expect: 23 passed, 1 skipped

cd ../Evaluation && .venv/bin/python -m pytest tests/ -q
# expect: 16 passed

# 2. Verify the v2 experiment data is intact
ls outputs/experiment/summaries/*/Ours_v2.json | wc -l       # → 7
ls outputs/experiment/evals_strict/*/Ours_v2.eval.json | wc -l  # → 7
ls outputs/experiment/evals_deberta/*/Ours_v2.eval.json | wc -l # → 7

# 3. Reproduce the v1-vs-v2 comparison
.venv/bin/python -m experiment.compare_v1_v2
# expect output matching §3 above (Mean ΔF1 +0.123 strict-LLM, +0.108 DeBERTa)

# 4. Check B6 baseline scaffolding is in place
grep -n "B6_llama_v2prompt" experiment/baselines.py
# expect 1 BASELINES entry + the prompt template
```

If all 4 checks pass, you're aligned with the previous chat's state.

---

## 7. Recommended order of operations

1. Run §6 sanity check.
2. Run §4.1 (B6 ablation, ~10 min).
3. Run §4.2 (analyse the 2×2).
4. Decide: is the v2 win prompt-engineering, architecture, or both?
5. Update `paper/main.tex` accordingly.
6. (Optional) Fix PaLM 2 recall-checker batching.
7. Commit + push to PR #2.

If at any step the user wants to discuss the result before
continuing — pause, summarise, ask. Don't run the full $n=29$ v2 reroll
without explicit user approval (that's $\sim$\$3-5).

---

## 8. References

-  Original spec: `HANDOFF.md` (top level)
-  v2 architecture changes: `RefinedSummarization/CHANGELOG_V2.md`
-  Paper draft: `RefinedSummarization/paper/main.tex`
-  External-review handoff: `RefinedSummarization/paper/PAPER_HANDOFF.md`
-  Stats: `RefinedSummarization/paper/stats.json`
-  Run logs: `Evaluation/outputs/experiment/*.log`
-  PR #2: https://github.com/KrimsonSun/AutoArxivSummarization/pull/2
