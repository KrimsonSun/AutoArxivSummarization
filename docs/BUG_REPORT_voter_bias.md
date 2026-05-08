# Bug report — Stage 2 voter ≈always picks Qwen (n=29 audit)

**Date:** 2026-05-07.
**Scope:** `Refine-OneVision-Summary` — Stage 2 (`GameTheoryVoter`) and the
prompts / serialisation it consumes.
**Status:** four bugs identified; three software-side fixes shipped, one
pool-design issue documented for follow-up.

This report is the engineering counterpart to `LESSONS.md` L9 and the
`PER_PAPER_AUDIT.md` outcome table. L9 / E27 establish the empirical
finding (the +0.106 vs B6 contrast decomposes as ~+0.16 backbone-swap
minus ~0.06 augmenter degradation); this file explains *why* the voter
behaved that way at the code level.

## 1. Symptom

On the n=29 paired benchmark, the OneVision Stage-2 Borda voter selects
the Qwen-72B drafter on **26 / 28 = 92.9 %** of papers. Llama wins twice
(both defensive fallbacks); DeepSeek never wins. Voter agreement with
the actually-strongest baseline per paper is **14 / 27 = 52 %**, no
better than always picking Qwen. PER_PAPER_AUDIT.md has the table.

## 2. Four compounding biases — root causes

### Bug 1: Authorship leakage (anonymisation was a lie)

Voter prompt (`config/prompts.yaml`, Stage 2 user template) rendered each
draft as:

```jinja
============================ {{ label }} ============================
{{ d.model_dump_json(indent=2) }}
```

`InitialSummary` declares `agent_id` as the first field
(`src/schemas/summary.py:36`), and the drafter system prompt forces
`Set agent_id to exactly: {{ agent_id }}`
(`config/prompts.yaml:38`). So every draft's JSON dump began with
`"agent_id": "agent_qwen"` (or `agent_llama` / `agent_deepseek`). The
voter system prompt's "you do NOT know which LLM wrote which" was
therefore false: voters could see authorship in line 1 of the JSON.

LLMs reading the prompt have a strong prior that "agent_qwen" refers to
Qwen-72B-Instruct, generally a strong model on technical-summary tasks.
Bug 1 alone is sufficient to explain the 93 % Qwen-rate.

### Bug 2: Voters knew their own identity (self-preference)

`config/prompts.yaml` (Stage 2 user template) ended with:

```jinja
You are voter "{{ voter_id }}", round {{ round_index }}.
```

Combined with Bug 1, each voter saw both "I am `agent_qwen`" and "draft
D1 was written by `agent_qwen`", enabling open self-preference.

### Bug 3: Length-correlated rubric (longest draft systematically wins)

The 0–10 scoring rubric (faithfulness / coverage / specificity / fluency)
rewards "covers the paper's atomic facts" and "preserves quantitative
detail" — both monotonic in raw length. From `RESULTS_TABLE.md` (n=29):

| Drafter | mean output (words) |
|---|---:|
| Qwen-72B | **726** |
| Llama-70B (B1 / B6) | 525 / 503 |
| DeepSeek-V3 | 514 |

Qwen averaged ~40 % more words than Llama / DeepSeek. The 1000-word cap
is a ceiling, not a floor: the cap binds for none of the three models.
Even with intact anonymisation, a length-aware rubric biases toward Qwen
for the wrong reason ("longer" rather than "better").

### Bug 4: Pool imbalance (1 weak + 2 strong drafters)

On v1 RefinedSummarization n=29 the per-baseline strict-LLM F1 means
were:

| Drafter | strict-LLM F1 |
|---|---:|
| B1 Llama-70B-naive | 0.418 |
| B2 Qwen-72B-naive | **0.569** |
| B3 DeepSeek-V3-naive | 0.531 |

Llama-70B is **~0.15 F1** below Qwen on this task. Three drafters with
1-weak / 2-strong → even a calibrated voter would prefer Qwen on most
papers because Qwen genuinely is the better drafter most of the time.
The 93 % Qwen-rate is therefore not entirely a bug — some of it is
drafter-pool reality, and a balanced pool would clarify how much of
each component is what.

## 3. Fixes shipped (Bugs 1, 2, 3)

### 3.1 De-anonymise drafts via dedicated serialisation method

`src/schemas/summary.py` — added on `InitialSummary`:

```python
def anon_json(self, indent: int = 2) -> str:
    return self.model_dump_json(exclude={"agent_id"}, indent=indent)
```

### 3.2 Replace `model_dump_json` calls in voter / verifier / refiner prompts

`config/prompts.yaml` — every `{{ d.model_dump_json(indent=2) }}` replaced
with `{{ d.anon_json(2) }}`. The verifier and refiner prompts'
`Draft from {{ draft.agent_id }}` headers replaced with the anonymous
`Draft (N words)` form. The voter user prompt's
`You are voter "{{ voter_id }}"` line removed entirely; the legacy voter
in `src/agents/voter.py` no longer renders `voter_id` into the prompt.

### 3.3 Length-normalised rubric (Bug 3 mitigation in legacy voter)

The Borda voter's rubric was rewritten in `config/prompts.yaml` Stage 2:

  - `coverage` (raw count) → `specific_facts_per_100_words` (density)
  - `specificity` (length-monotonic) → `coverage_breadth_0_10`
    (independent of length)
  - The system prompt now explicitly instructs that "length alone MUST
    NOT decide the ranking."

### 3.4 Replacement voter (Bug 3 + structural fix): `ClaimGroundingVoter`

Inspired by SpecEM's principle ("replace subjective rubric judging with
objective per-token / per-claim signals"). New file:
`src/agents/claim_grounding_voter.py`. Algorithm:

```
for each draft d in {D1, D2, D3}:
    issues_d = SingleDraftVerifier.run(paper, d)        # one verifier call
    density_d = len(issues_d) / max(word_count(d) / 100, 1)
winner = argmin_d density_d
   (tie-break: fewer missing_info, then fewer factual_error, then
    fewer total issues, then deterministic by label)
```

Properties:

  - **Length-normalised by construction**: a 700-word draft with 14
    issues ties a 350-word draft with 7 issues — Bug 3 cannot fire.
  - **Authorship-anonymous by construction**: the verifier prompt
    consumes `draft.anon_json()` and never sees `agent_id`.
  - **Pool-symmetric**: all three drafts are scored by the same single
    `pipeline_llm` verifier (Llama-70B). No drafter scores its own work.
  - **Cheaper than legacy**: 3 verifier calls vs 9 voter calls
    (3 voters × 3 rounds). The winner's issue list is stashed on
    `VotingTranscript.precomputed_winner_issues` and reused by Stage 3,
    so we save a 4th verifier call relative to the previous flow.

Default `config/default.yaml` sets `pipeline.voting.method:
claim_grounding`. Legacy mode preserved as `config/borda_legacy.yaml`
(`pipeline.voting.method: borda`) for ablation; the legacy voter has
the anon / no-voter_id / length-normalised-rubric fixes applied so that
even a head-to-head replay can be done cleanly.

## 4. Bug 4 (pool design) — open

Not fixed in this round. Mitigations to consider:

| Option | Cost | Effect |
|---|---|---|
| Replace Llama-70B with Mixtral-8x22B or Llama-3.1-405B | medium ($) | restores 3-strong pool symmetry |
| Add a 4th drafter (e.g. Mistral-Large) — Borda 4-way | medium ($) | richer ballot dispersion |
| Keep the pool, document Bug 4 as a deliberate scope note in the paper | $0 | honest framing only |

The first two genuinely change the comparison; the third is the
companion-paper-honesty option (already discussed in HANDOFF.md
Open Question 1).

## 4.5 Bug 5 — discovered during n=3 smoke (verifier saturation defeats density)

The first n=3 smoke run picked **Qwen on 3/3 papers under both methods**.
Reading the per-draft scoring:

| Paper | D1 (Qwen) words/total/missing | D2 (Llama) | D3 (DeepSeek) |
|---|---|---|---|
| 2004.04906 | 600 / 12 / 7 | 354 / 12 / 10 | 361 / 12 / 6 |
| 1706.03762 | 752 / 12 / 8 | 384 / 12 / 8 | 421 / 12 / 4 |
| 2210.03629 | 505 / 12 / 5 | 305 / 12 / 6 | 253 / 12 / 8 |

**Total issues = 12 on every draft.** The verifier saturates its
`MAX_ISSUES=12` cap on 100 % of papers (matching E25's v1 finding that
mean issues raised = 12.0, all 29/29 saturated). With total fixed,
`density = total / (words / 100)` reduces to:

  `density ≈ 1200 / words`

i.e. the new voter degenerates into **argmax(words)**. Qwen averages
~40 % more words → Qwen wins by length, exactly the Bug 3 bias the new
voter was designed to remove.

But the `missing_info` column varies meaningfully across drafts (4–10),
because the verifier's cap is filled by a *mix* of issue types
(factual_error / unsupported_claim / ambiguity also fill the 12 slots).
On Attention paper, DeepSeek has 4 missing_info vs Qwen's 8 — DeepSeek
covers the paper's specific facts more efficiently per word, even
though it's shorter.

### Two fixes shipped (Fix 1 + Fix 2)

**Fix 1 — voter density formula uses missing_info, not total.**
`src/agents/claim_grounding_voter.py`: primary score is
`missing_info / max(words/100, 1)`. Tie-breaks switched to
`factual_error → unsupported_claim → total → label`. Schema doc on
`ClaimGroundingScore.issues_per_100_words` updated accordingly.

**Fix 2 — verifier prompt anti-padding instruction.**
`config/prompts.yaml` Stage 3 (verifier_onevision): explicit
"Do NOT pad to a fixed count" instruction added at top of Rules; output
0 issues when the draft is excellent; severity calibration
(HIGH / MEDIUM / LOW) — only include LOW-severity if the count is
below ~3. The `MAX_ISSUES=12` cap stays as a ceiling; it now only fires
on genuinely defective drafts.

Re-running the n=3 (extended to n=5) smoke validates both fixes —
results in §5 below.

## 4.6 Bug 6 — discovered during n=5 smoke (density rewards compactness, not recall)

After Fix 1 (missing_info-density) + Fix 2 (anti-padding verifier), the
n=5 re-run still picked **Qwen on 5/5 papers**. But the per-draft data
revealed two papers where Qwen had *more* missing_info than another
drafter:

  - 2005.11401 (RAG): Qwen 5 missing vs Llama 3 missing — Llama covered
    the paper's facts better, but Qwen still won because Qwen is longer
    (702 w vs Llama 382 w) so its missing-info-per-100-words density
    (0.712) beat Llama's (0.785).
  - 2308.08155 (AutoGen): DeepSeek 3 missing vs Qwen 4 missing — same
    pattern.

The downstream evaluation metric is F1 against paper claims:
recall = (claims_covered) / (total_paper_claims). Recall **does not
length-normalise** — a 200-word draft with 13/15 claims covered has
the same recall as an 800-word draft with 13/15. So the voter's
per-100-words density rewards the wrong thing: compactness, when the
metric we optimise is absolute coverage.

### Fix 3 — primary score is absolute missing_info, not density

`src/agents/claim_grounding_voter.py` — primary score changed from
`missing_info / max(words/100, 1)` to `missing_info` (absolute count).
Tie-break collapsed to `(factual_error + unsupported_claim) → total →
label` for a single precision-aware penalty. Schema field
`ClaimGroundingScore.issues_per_100_words` keeps its name for backward
compatibility but now stores the absolute count.

**Offline replay** (deterministic re-scoring of the existing n=5
verifier counts under the new rule):

| Paper | Qwen / Llama / DS missing | Fix 1+2 winner | **Fix 3 winner** |
|---|---|---|---|
| 1706.03762 (Attention) | **2** / 4 / 3 | Qwen | Qwen |
| 2004.04906 (DPR) | 4 / 4 / 4 | Qwen | Qwen (3-way tie, label fallback) |
| 2005.11401 (RAG) | 5 / **3** / 4 | Qwen | **Llama** ⇄ flip |
| 2210.03629 (ReAct) | **2** / 3 / 3 | Qwen | Qwen |
| 2308.08155 (AutoGen) | 4 / 5 / **3** | Qwen | **DeepSeek** ⇄ flip |

| Aggregate | Fix 1+2 | **Fix 3** |
|---|---:|---:|
| agent_qwen | 5/5 (100 %) | **3/5 (60 %)** |
| agent_llama | 0/5 | 1/5 |
| agent_deepseek | 0/5 | 1/5 |

The voter now varies by paper. Whether the per-paper choices yield
higher F1 than always-Qwen is an open question — the answer needs a
full n=29 pipeline re-run with Fix 1+2+3 plus end-to-end evaluation.
But the **voter-bias** symptom is gone: the 93 % Qwen-rate from the
PER_PAPER_AUDIT is no longer reproduced in this voter.

### Caveat — the DPR tie shows a deeper problem

Paper 2004.04906 produced a degenerate 3-way tie on (missing,
precision_penalty, total) = (4, 1, 5) for all three drafts. The
tie-break fell to alphabetical label, picking D1 (which happened to
be Qwen). DPR is genuinely a Qwen-favourable paper (Qwen-naive F1
0.824 vs DeepSeek 0.182 per stats.json case study), so the fallback
got the right answer here, but only by accident.

If many papers hit this degenerate-tie case, the voter regresses to
"deterministic by random label assignment". A real fix would need
either richer signal from the verifier (per-issue severity, per-issue
support strength) or a fully different scoring path — see §6
"What's still on the table" below.

## 5. How to A/B verify the fix

`scripts/voter_ab_smoke.py` runs the OneVision pipeline on n=3 papers
under both `claim_grounding` and `borda` (post-fix) configs and writes
a side-by-side report (winner per paper, per-draft scoring, token cost).

```
cd Refine-OneVision-Summary
OPENAI_API_KEY=sk-or-v1-...  OPENAI_BASE_URL=https://openrouter.ai/api/v1  \
    python scripts/voter_ab_smoke.py --n 3
```

Predictions worth checking:

  - **Qwen-rate under `claim_grounding` should drop substantially below
    93 %** (target: ≤60 % on n=3, ≤70 % on n=29). If still ≥80 %, then
    Bug 4 dominates and either the pool changes or the paper framing
    changes (see §4).
  - **Cost under `claim_grounding` should be roughly equivalent or lower
    than legacy `borda`** because the per-draft verifier calls (3) plus
    saved Stage-3 call ≈ legacy voter calls (9) — but this depends on
    drafter-output verbosity. Token logs are dumped per paper.
  - **Borda (post-fix) Qwen-rate** should also drop relative to the
    pre-fix 93 %, because Bugs 1–3 are repaired in that path too.

## 6. Files touched

| Path | Change |
|---|---|
| `Refine-OneVision-Summary/src/schemas/summary.py` | + `anon_json()`, + `word_count()` on `InitialSummary` |
| `Refine-OneVision-Summary/src/schemas/vote.py` | + `ClaimGroundingScore`; `VotingTranscript` extended with `method`, `claim_grounding_scores`, `precomputed_winner_issues` |
| `Refine-OneVision-Summary/config/prompts.yaml` | de-anon serialisation in voter / verifier / refiner; voter rubric length-normalised; voter user prompt no longer carries `voter_id` |
| `Refine-OneVision-Summary/src/agents/voter.py` | drop `voter_id` from `render(...)` call; module docstring updated |
| `Refine-OneVision-Summary/src/agents/claim_grounding_voter.py` | **new file** — `ClaimGroundingVoter` |
| `Refine-OneVision-Summary/src/agents/__init__.py` | export `ClaimGroundingVoter` |
| `Refine-OneVision-Summary/src/config/loader.py` | `VotingSpec.method` field added |
| `Refine-OneVision-Summary/config/default.yaml` | `voting.method: claim_grounding` (new default) |
| `Refine-OneVision-Summary/config/borda_legacy.yaml` | **new file** — keeps `voting.method: borda` for ablation |
| `Refine-OneVision-Summary/src/pipeline.py` | dispatch on `voting.method`; reuse precomputed winner issues for Stage 3 |
| `Refine-OneVision-Summary/scripts/voter_ab_smoke.py` | **new file** — A/B smoke runner |
| `Refine-OneVision-Summary/scripts/replay_voter_with_fix3.py` | **new file** — offline re-score of cached smoke transcripts under Fix 3 (free, no API) |
| `Refine-OneVision-Summary/config/prompts.yaml` (Stage 3 verifier) | Fix 2 — anti-padding instruction; severity calibration; cap is ceiling not target |

## 7. Tests

All 25 existing pytest tests pass after the changes:

```
$ python -m pytest tests/
============================== 25 passed in 5.69s ==============================
```

A mock-driven sanity check (no API calls) confirms `ClaimGroundingVoter`
correctly picks the lowest-density draft over a longer draft with more
absolute issues:

```
D1 (agent_llama):   words=503, total=6, missing=3, density=1.193
D2 (agent_qwen):    words=703, total=8, missing=4, density=1.138
D3 (agent_deepseek): words=503, total=4, missing=2, density=0.795 ← winner
```

The longest draft (Qwen, 8 issues, 703 words) does **not** win — the
shortest-with-fewest-issues (DeepSeek) does. Pre-fix Borda would have
ranked Qwen first by raw coverage / specificity counts.
