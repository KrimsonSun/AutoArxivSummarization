"""Schemas for the game-theory voter (Stage 2 of Refine-OneVision pipeline).

The voter runs 3 rounds of cross-evaluation among 3 LLMs. In each round,
each LLM ranks the 3 drafts (anonymously labelled D1 / D2 / D3) on a
shared rubric. After 3 rounds, we aggregate via Borda count and pick
the winning draft.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


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


class VotingTranscript(BaseModel):
    """Full record of all rounds across all voters; orchestrator-built."""

    voter_ids: list[str]
    label_to_agent: dict[str, str] = Field(
        description=(
            "Mapping of anonymous draft label (D1/D2/D3) to the actual "
            "agent_id of the LLM that produced it. Withheld from the voters "
            "during voting; recorded here for post-hoc inspection."
        )
    )
    rounds: list[list[RankingResult]] = Field(
        description="Outer list indexed by round (0..K-1); inner by voter."
    )
    winner_label: str = Field(pattern=r"^D[123]$")
    winner_agent_id: str
    winner_total_borda: float
    per_label_borda: dict[str, float] = Field(
        description="Borda totals per draft label across all voters/rounds."
    )
