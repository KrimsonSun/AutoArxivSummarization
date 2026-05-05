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

__all__ = [
    "Contribution",
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
]
