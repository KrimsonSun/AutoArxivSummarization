"""Schemas for initial drafts and the final merged summary (handoff §2.2, §2.5)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Contribution(BaseModel):
    text: str
    evidence_refs: list[str] = Field(default_factory=list)


class MethodComponent(BaseModel):
    name: str
    description: str
    evidence_refs: list[str] = Field(default_factory=list)


class MethodBlock(BaseModel):
    overview: str
    components: list[MethodComponent] = Field(default_factory=list)


class ExperimentFinding(BaseModel):
    text: str
    evidence_refs: list[str] = Field(default_factory=list)


class ExperimentsBlock(BaseModel):
    setup: str
    key_findings: list[ExperimentFinding] = Field(default_factory=list)


class InitialSummary(BaseModel):
    """One of three initial drafts. Schema matches FinalSummary minus metadata."""

    agent_id: str
    tldr: str
    core_idea: str
    key_contributions: list[Contribution] = Field(default_factory=list)
    method: MethodBlock
    experiments: ExperimentsBlock
    limitations: list[str] = Field(default_factory=list)


class FinalSummaryMetadata(BaseModel):
    arxiv_id: str | None = None
    title: str
    paper_paragraph_count: int
    initial_agents: list[str]
    pipeline_llm: str
    verification_mode: str = "mutual_peer_review"
    issues_raised: int = 0
    issues_addressed: list[str] = Field(default_factory=list)
    evidence_paragraphs_used: list[str] = Field(default_factory=list)
    timestamp: str
    total_llm_calls: int = 0
    total_tokens_used: dict[str, int] = Field(
        default_factory=lambda: {"prompt": 0, "completion": 0}
    )
    truncated: bool = False
    failed_initial_agents: list[str] = Field(
        default_factory=list,
        description="Agent IDs whose initial summary failed (handoff §8).",
    )
    consensus_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "How many issues were raised by 1 / 2 / 3+ reviewers in "
            "mutual_peer_review mode. In single_judge mode all issues land "
            "under the 'judge' bucket. Used as an evaluation signal: high "
            "consensus on many issues = drafts have shared deficiencies; "
            "low consensus = each model has unique blind spots."
        ),
    )


class FinalSummary(BaseModel):
    """The output of the refiner stage — what the consumer ultimately receives."""

    tldr: str
    core_idea: str
    key_contributions: list[Contribution] = Field(default_factory=list)
    method: MethodBlock
    experiments: ExperimentsBlock
    limitations: list[str] = Field(default_factory=list)
    metadata: FinalSummaryMetadata
