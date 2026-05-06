"""Pydantic schemas for the debate pipeline.

All cross-stage I/O is strongly typed. Schemas correspond to handoff §2.
"""
from src.schemas.evidence import EvidenceBundle, EvidenceItem
from src.schemas.issue import Issue, IssueType
from src.schemas.paper import Paragraph, ParsedPaper
from src.schemas.summary import (
    Contribution,
    ExperimentFinding,
    ExperimentsBlock,
    FinalSummary,
    FinalSummaryMetadata,
    InitialSummary,
    MethodBlock,
    MethodComponent,
)
from src.schemas.vote import (
    DraftScore,
    RankingResult,
    VoteList,
    VotingTranscript,
)

__all__ = [
    "Contribution",
    "DraftScore",
    "EvidenceBundle",
    "EvidenceItem",
    "ExperimentFinding",
    "ExperimentsBlock",
    "FinalSummary",
    "FinalSummaryMetadata",
    "InitialSummary",
    "Issue",
    "IssueType",
    "MethodBlock",
    "MethodComponent",
    "Paragraph",
    "ParsedPaper",
    "RankingResult",
    "VoteList",
    "VotingTranscript",
]
