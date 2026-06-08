# AGENTS.md — AutoArxivSummarization

This file is the persistent root-level briefing for any Codex
session in this repo. Keep it ≤ 100 lines. Detailed state lives in
`docs/`.

## What this project is

A **research project + engineering submodule** mixed:

- **Research.** Two papers, both LaTeX, both standalone, both kept
  independent (don't merge them):
  - `RefinedSummarization/paper/` — *negative-result paper*. The v1
    multi-agent debate pipeline loses to single-LLM baselines.
  - `Refine-OneVision-Summary/paper/` — *companion follow-up*. A
    redesigned vote-then-augment pipeline; recovers a within-family
    architectural contribution but does not exceed cross-family
    single-LLM baselines.

- **Engineering.** Three Python modules that the main
  `AutoArxivSummarization` Next.js app calls as subprocesses:
  - `RefinedSummarization/` — v1/v2 pipeline. **Frozen** for paper
    reproducibility.
  - `Refine-OneVision-Summary/` — v3 / OneVision pipeline. **Active.**
  - `Evaluation/` — shared evaluator + experiment harness. **Active.**

  The TS↔Python contract: `python -m src.cli` writes JSON to stdout,
  logs to stderr. See `docs/KNOWN_ISSUES.md` K2/K3.

## Working principles

1. **Test-first inside the engineering modules.** `pytest` must pass
   before any `git push`. The test directories are
   `Refine-OneVision-Summary/tests/`, `Evaluation/tests/`, and
   `RefinedSummarization/tests/`.
2. **Don't change `LESSONS`-protected design.** If a piece of design
   is justified by a lesson in `docs/LESSONS.md`, don't undo it
   without (a) reading the lesson, (b) writing a new lesson that
   supersedes it.
3. **Before any new experiment**, search `docs/EXPERIMENTS.json` for a
   prior run of the same hypothesis. Do not re-run a `concluded_*`
   experiment without a clear new hypothesis. The existing entries
   are the project's ground truth on what we know.
4. **Paper-level decisions** (framing, scoping, target venue, what
   goes in `paper/main.tex`) live in `docs/PAPER_PLAN.md`.
   **Implementation-level decisions** (architecture, prompt design,
   pipeline contracts) reference `docs/PIPELINE_SPEC.md` (which is a
   v1→v2 historical snapshot, not a current spec — see
   `docs/HANDOFF.md` Part A.3).
5. **All API keys** live in a single `.env` at the repo root, picked
   up by all three subprojects via the walk-up settings loader. See
   `docs/KNOWN_ISSUES.md` K1. Don't put keys in any project-local
   `.env`.

## Where to find things

| You need… | Read… |
|---|---|
| Current state of the project (what's running, what's locked) | `docs/HANDOFF.md` Part B |
| Documentation contract (when to edit which file) | `docs/HANDOFF.md` Part A |
| A paired-CI / F1 / metric number | `docs/EXPERIMENTS.json` |
| Why a piece of design is the way it is | `docs/LESSONS.md` |
| An environment / install / API gotcha | `docs/KNOWN_ISSUES.md` |
| Paper framing / venue / review feedback | `docs/PAPER_PLAN.md` |
| What the v1→v2 transition looked like | `docs/PIPELINE_SPEC.md` |
| Project roadmap, target conferences, go/no-go on arXiv | `PLAN.md` |
| What `/compact` should preserve | `docs/COMPACTION_PROMPT.md` |
| Side-by-side architecture diagrams (synthesis vs selection-augment) | `docs/ARCHITECTURES.md` |
| OneVision per-paper outcome audit (n=29) | `docs/PER_PAPER_AUDIT.md` |

## Discipline (every session)

- **Start.** Read `docs/HANDOFF.md` Part B. Skim `docs/LESSONS.md`.
- **During.** Append to the right file when you learn something new
  (LESSONS / EXPERIMENTS.json / KNOWN_ISSUES). Don't edit existing
  entries; add new ones.
- **End.** Rewrite `docs/HANDOFF.md` Part B with the new current
  state. Update `PLAN.md` only if the project stage changed.

## Don'ts

- Don't merge the two papers. They serve different purposes.
- Don't run a long-form experiment without a per-call timeout — see
  KNOWN_ISSUES K8 (the OneVision v2 run on n=29 stalled on 5 long
  papers because no timeout was configured).
- Don't claim "multi-agent debate fails" without scoping (LESSON L7).
- Don't claim the architecture-vs-prompt question is "settled" by
  the n=6 ablation — that was overturned at n=29 (LESSON L8 → L9).
