"""Schemas for retriever output (handoff §2.4)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    paragraph_id: str = Field(pattern=r"^P\d+$")
    text: str = Field(
        description=(
            "Paragraph text. Filled in code from ParsedPaper, NOT generated "
            "by the LLM (handoff §2.4 anti-hallucination rule)."
        )
    )
    relevance_explanation: str


class EvidenceBundle(BaseModel):
    issue_id: str = Field(pattern=r"^I\d+$")
    evidence: list[EvidenceItem] = Field(default_factory=list)


class EvidenceSelection(BaseModel):
    """LLM-facing schema. The retriever returns paragraph IDs + explanations
    only. The text is filled in by code afterwards.
    """

    paragraph_id: str = Field(pattern=r"^P\d+$")
    relevance_explanation: str


class EvidenceSelectionList(BaseModel):
    """Wrapper for the retriever LLM's structured output."""

    selections: list[EvidenceSelection] = Field(default_factory=list)
