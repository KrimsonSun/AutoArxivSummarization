"""Schemas for Stage 2 voting / draft selection.

Two voting methods share this transcript shape:

  • "borda" (legacy) — 3 LLMs do K rounds of cross-evaluation under a
    rubric. Aggregated via Borda. Anonymisation fixed in v2 (see
    docs/BUG_REPORT_voter_bias.md): drafts dumped without `agent_id`
    and voters do not see their own `voter_id`.

  • "claim_grounding" (default in v2) — replaces LLM judging with the
    verifier output. Each draft is run through the SingleDraftVerifier
    once; the draft with the lowest issue-per-100-words density wins.
    Length-normalised, length-anonymous, and authorship-anonymous by
    construction. Inspired by SpecEM's principle of replacing subjective
    rubric judging with objective per-token / per-claim signals.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.issue import Issue


class DraftScore(BaseModel):
    """One LLM's verdict on one draft."""

    draft_label: str = Field(
        pattern=r"^D[123]$",
        description="Anonymous label assigned by the orchestrator (D1/D2/D3).",
    )
    rank: int = Field(
        ge=1, le=3, description="1 = best, 3 = worst (no ties allowed)."
    )
    faithfulness_0_10: int = Field(ge=0, le=10)
    coverage_0_10: int = Field(ge=0, le=10)
    specificity_0_10: int = Field(ge=0, le=10)
    fluency_0_10: int = Field(ge=0, le=10)
    rationale: str = Field(
        max_length=600,
        description="One short paragraph justifying the rank + scores.",
    )


class RankingResult(BaseModel):
    """One LLM's ranking of all 3 drafts in one round."""

    voter_id: str = Field(description="Which LLM produced this ranking.")
    round_index: int = Field(ge=1, le=3)
    scores: list[DraftScore] = Field(
        min_length=3,
        max_length=3,
        description="Exactly 3 DraftScore entries, one per draft.",
    )
    is_abstention: bool = Field(
        default=False,
        description=(
            "True if this voter's call failed or returned invalid output for "
            "this round. Abstentions are excluded from Borda aggregation."
        ),
    )


class VoteList(BaseModel):
    """Used as the structured output of one voter call (one round)."""

    scores: list[DraftScore] = Field(min_length=3, max_length=3)


class ClaimGroundingScore(BaseModel):
    """Per-draft scoring under the claim-grounding voter."""

    draft_label: str = Field(pattern=r"^D[123]$")
    agent_id: str = Field(
        description=(
            "Author of this draft. Recorded for transcript bookkeeping only; "
            "the verifier never sees this field."
        )
    )
    word_count: int = Field(ge=0)
    n_factual_error: int = Field(ge=0)
    n_missing_info: int = Field(ge=0)
    n_unsupported_claim: int = Field(ge=0)
    n_ambiguity: int = Field(ge=0)
    n_total_issues: int = Field(ge=0)
    issues_per_100_words: float = Field(
        description=(
            "DEPRECATED-NAME — this field stores the absolute missing_info "
            "count cast to float, NOT a per-100-words density. Lower = "
            "better; this is the value the voter argmin-selects on. The "
            "field name is kept for transcript schema backward "
            "compatibility. Density-based scoring was discarded after the "
            "n=5 smoke (BUG_REPORT_voter_bias.md §4.5 / §4.6) because it "
            "rewards compactness rather than recall, while the downstream "
            "F1 metric is recall-aligned (claims_covered / total_paper_claims, "
            "no length normalisation)."
        )
    )


class VotingTranscript(BaseModel):
    """Full record of all rounds across all voters; orchestrator-built."""

    method: str = Field(
        default="borda",
        description="Voting method: 'borda' | 'claim_grounding' | 'trivial_fallback'.",
    )
    voter_ids: list[str]
    label_to_agent: dict[str, str] = Field(
        description=(
            "Mapping of anonymous draft label (D1/D2/D3) to the actual "
            "agent_id of the LLM that produced it. Withheld from the voters "
            "during voting; recorded here for post-hoc inspection."
        )
    )
    rounds: list[list[RankingResult]] = Field(
        description="Outer list indexed by round (0..K-1); inner by voter. Empty for non-Borda methods."
    )
    winner_label: str = Field(pattern=r"^D[123]$")
    winner_agent_id: str
    winner_total_borda: float
    per_label_borda: dict[str, float] = Field(
        description="Borda totals per draft label across all voters/rounds. Empty/zero for non-Borda methods."
    )
    # Claim-grounding-specific fields (None for borda / trivial_fallback).
    claim_grounding_scores: list[ClaimGroundingScore] | None = Field(
        default=None,
        description="Per-draft issue-density scores when method=='claim_grounding'.",
    )
    precomputed_winner_issues: list[Issue] | None = Field(
        default=None,
        description=(
            "Verifier issues already computed on the winning draft as a "
            "side-effect of voting (claim_grounding mode). Pipeline reuses "
            "these for Stage 3 instead of re-running the verifier."
        ),
    )
