"""Schemas for the parsed paper (handoff §2.1)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SectionName = Literal[
    "Abstract",
    "Introduction",
    "Method",
    "Experiments",
    "Conclusion",
    "Other",
]


class Paragraph(BaseModel):
    """One paragraph of the source paper.

    `id` is a globally-monotonic identifier (P1, P2, ...) that does NOT reset
    across sections. Every downstream agent references paragraphs by this id.
    """

    id: str = Field(pattern=r"^P\d+$")
    section: SectionName
    text: str
    summary_short: str | None = Field(
        default=None,
        description=(
            "~200-char summary of `text`, pre-generated to keep retriever "
            "prompts compact. None if not yet computed."
        ),
    )


class ParsedPaper(BaseModel):
    """The full structured representation of a paper after PDF parsing."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str
    paragraphs: list[Paragraph] = Field(default_factory=list)
    arxiv_id: str | None = None

    def paragraph_by_id(self, pid: str) -> Paragraph | None:
        for p in self.paragraphs:
            if p.id == pid:
                return p
        return None
