"""ClaimGroundingVoter — Stage 2 default voting method (v2).

Replaces the legacy LLM-judging Borda voter. Per-paper audit on n=29 (see
docs/BUG_REPORT_voter_bias.md and docs/PER_PAPER_AUDIT.md) showed the
Borda voter picked Qwen on 26 / 28 papers (≈93 %) due to four compounding
biases:

  1. Authorship leakage   — agent_id was the first key in each draft's
                            JSON dump that voters saw, so D1/D2/D3 were
                            in fact de-anonymised.
  2. Self-preference       — voter_id was rendered into the prompt, so
                            voters could vote for their own draft.
  3. Length confound       — coverage / specificity rubrics correlated
                            with raw length, and Qwen's drafts averaged
                            ≈40 % more words than Llama / DeepSeek's.
  4. Pool imbalance        — Llama-70B's mean F1 is ≈0.15 below Qwen-72B
                            on this task; with 3 drafters the pool was
                            1-weak / 2-strong rather than balanced.

Bugs 1–3 are software defects we can fix; Bug 4 is a pool-design choice.

This voter, inspired by SpecEM's principle ("replace subjective rubric
judging with objective per-token / per-claim signals"), drops the LLM
ranking entirely:

    for each draft d in {D1, D2, D3}:
        issues_d = SingleDraftVerifier.run(paper, d)
                   # The verifier prompt was already patched to dump the
                   # draft via anon_json() — it never sees agent_id.
        density_d = len(issues_d) / max(word_count(d) / 100, 1)
                   # Length-normalised: a 700-word draft with 14 issues
                   # ties a 350-word draft with 7 issues.

    winner = argmin_d density_d   (tie-break by n_missing_info, then
                                   n_factual_error, then n_total)

Cost note: stage 2 runs 3× verifier calls (one per draft) instead of
9 LLM calls (3 voters × 3 rounds). Net cost: lower than legacy. The
winner's issues are stashed on VotingTranscript.precomputed_winner_issues
so pipeline.py reuses them for Stage 3 rather than re-running the verifier.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from src.agents.verifier import SingleDraftVerifierAgent
from src.llm_clients.base import LLMClient
from src.schemas.issue import Issue, IssueType
from src.schemas.paper import ParsedPaper
from src.schemas.summary import InitialSummary
from src.schemas.vote import (
    ClaimGroundingScore,
    VotingTranscript,
)


@dataclass
class _DraftScoring:
    label: str
    draft: InitialSummary
    issues: list[Issue]
    density: float


class ClaimGroundingVoter:
    """Verifier-driven, length-normalised, anonymous Stage 2 voter.

    Parameters
    ----------
    verifier
        SingleDraftVerifierAgent — already wired to the pipeline_llm
        client. Same instance is used to score every draft, guaranteeing
        symmetric, judge-pool-independent treatment.
    seed
        Seed for the D1/D2/D3 label permutation (cosmetic; the voter
        does not consume the labels — they are for transcript symmetry
        with the legacy Borda voter).
    """

    def __init__(self, verifier: SingleDraftVerifierAgent, seed: int = 42):
        self.verifier = verifier
        self.rng = random.Random(seed)

    async def run(
        self, paper: ParsedPaper, drafts: list[InitialSummary]
    ) -> VotingTranscript:
        if len(drafts) != 3:
            raise ValueError(
                f"ClaimGroundingVoter requires exactly 3 drafts; got {len(drafts)}"
            )

        # Anonymous labels D1/D2/D3 in random order — for transcript symmetry
        # with the legacy Borda voter. The verifier itself never sees these
        # labels (it gets the InitialSummary directly via anon_json), so the
        # mapping is cosmetic but kept for consistency in downstream tooling.
        order = ["D1", "D2", "D3"]
        self.rng.shuffle(order)
        label_to_agent: dict[str, str] = {
            order[i]: drafts[i].agent_id for i in range(3)
        }
        labelled: list[tuple[str, InitialSummary]] = [
            (order[i], drafts[i]) for i in range(3)
        ]
        labelled.sort(key=lambda lab_d: lab_d[0])

        # Run the verifier on each draft concurrently. The verifier prompt
        # was patched to use anon_json() so authorship cannot leak through.
        per_draft_issues: list[list[Issue]] = await asyncio.gather(
            *(self.verifier.run(paper, d) for _, d in labelled)
        )

        # Compute per-draft scoring.
        #
        # IMPORTANT — recall-aligned scoring. The downstream evaluation
        # metric is F1 against paper claims (precision × recall), and
        # F1's recall component does NOT length-normalise (recall =
        # claims_covered / total_paper_claims). Earlier iterations of
        # this voter used a per-100-words density to fight Bug 3
        # (length confound), but that hands the win to whichever draft
        # is most "compact" — which is the wrong objective. A 200-word
        # draft covering 13/15 paper claims and an 800-word draft
        # covering the same 13 claims have IDENTICAL F1, so the voter
        # must be indifferent between them.
        #
        # Hence: the primary score is the absolute missing_info count
        # the verifier reports on each draft. That is the count of
        # paper facts NOT covered by the draft — directly proportional
        # to (total_paper_claims − recall). The Fix 2 anti-padding
        # verifier prompt makes this a meaningful signal: the verifier
        # now reports actually-missing facts (typically 2–6 per draft)
        # rather than padding to MAX_ISSUES=12.
        #
        # Tie-breaks add a precision penalty: factual_error +
        # unsupported_claim count. A draft that covers the paper well
        # but fabricates extra claims should lose to a draft with the
        # same recall and no fabrications.
        scored: list[_DraftScoring] = []
        per_label_score: list[ClaimGroundingScore] = []
        for (label, draft), issues in zip(labelled, per_draft_issues):
            words = max(draft.word_count(), 1)
            n_total = len(issues)
            counts = _bucket_issues(issues)
            n_missing = counts["missing_info"]
            # Primary score: absolute missing_info count. Lower = better.
            scored.append(
                _DraftScoring(
                    label=label, draft=draft, issues=issues, density=float(n_missing)
                )
            )
            # Recorded for transcript bookkeeping; the schema field name
            # is preserved for backward compatibility but stores absolute
            # missing_info count now (see ClaimGroundingScore docstring).
            per_label_score.append(
                ClaimGroundingScore(
                    draft_label=label,
                    agent_id=draft.agent_id,
                    word_count=words,
                    n_factual_error=counts["factual_error"],
                    n_missing_info=n_missing,
                    n_unsupported_claim=counts["unsupported_claim"],
                    n_ambiguity=counts["ambiguity"],
                    n_total_issues=n_total,
                    issues_per_100_words=float(n_missing),
                )
            )

        # argmin absolute missing_info. Tie-break:
        #   1. fewer (factual_error + unsupported_claim) — precision penalty
        #   2. fewer total issues (catch-all)
        #   3. deterministic by label
        scored.sort(
            key=lambda s: (
                s.density,  # primary: absolute missing_info
                _bucket_issues(s.issues)["factual_error"]
                + _bucket_issues(s.issues)["unsupported_claim"],
                len(s.issues),
                s.label,
            )
        )
        winner = scored[0]

        # Borda totals are repurposed: `4 - rank` so the lowest-density
        # draft gets 3, next gets 2, last gets 1. Keeps downstream tooling
        # that expects a per_label_borda dict happy.
        per_label_borda: dict[str, float] = {}
        for rank, s in enumerate(scored, start=1):
            per_label_borda[s.label] = float(4 - rank)

        return VotingTranscript(
            method="claim_grounding",
            voter_ids=["claim_grounding_judge"],
            label_to_agent=label_to_agent,
            rounds=[],  # No LLM voter rounds in this method.
            winner_label=winner.label,
            winner_agent_id=winner.draft.agent_id,
            winner_total_borda=per_label_borda[winner.label],
            per_label_borda=per_label_borda,
            claim_grounding_scores=per_label_score,
            precomputed_winner_issues=list(winner.issues),
        )


def _bucket_issues(issues: list[Issue]) -> dict[str, int]:
    out = {
        "factual_error": 0,
        "missing_info": 0,
        "unsupported_claim": 0,
        "ambiguity": 0,
        "other": 0,
    }
    for i in issues:
        if i.type == IssueType.FACTUAL_ERROR:
            out["factual_error"] += 1
        elif i.type == IssueType.MISSING_INFO:
            out["missing_info"] += 1
        elif i.type == IssueType.UNSUPPORTED_CLAIM:
            out["unsupported_claim"] += 1
        elif i.type == IssueType.AMBIGUITY:
            out["ambiguity"] += 1
        else:
            out["other"] += 1
    return out
