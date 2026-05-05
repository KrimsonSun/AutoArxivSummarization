"""Pydantic schemas for the 4-step evaluation pipeline.

Step 1 (extractor)  → list[Claim]
Step 2 (retriever)  → list[EvidenceChunk] per claim
Step 3 (verifier)   → list[ClaimVerification]
Step 4 (scorer)     → EvaluationReport (the deliverable for the paper)
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# --------------------------------------------------------------------- inputs

class PaperParagraph(BaseModel):
    """One paragraph from the original paper."""

    id: str = Field(pattern=r"^P\d+$")
    text: str


class PaperBundle(BaseModel):
    """Everything the evaluator needs to know about the source paper."""

    arxiv_id: str | None = None
    title: str = ""
    paragraphs: list[PaperParagraph] = Field(default_factory=list)


# ---------------------------------------------------------------- step 1: claims

class Claim(BaseModel):
    """One atomic factual claim extracted from the summary."""

    id: str = Field(pattern=r"^C\d+$")
    text: str
    source_field: str | None = Field(
        default=None,
        description=(
            "Where in the summary this claim came from, e.g. 'tldr', "
            "'key_contributions[2]', 'method.overview'. Used for traceability."
        ),
    )


class ClaimList(BaseModel):
    """LLM-facing wrapper for structured-output claim extraction."""

    claims: list[Claim] = Field(default_factory=list)


# ------------------------------------------------------------- step 2: evidence

class EvidenceChunk(BaseModel):
    """A single retrieved paragraph + its retrieval score."""

    paragraph_id: str = Field(pattern=r"^P\d+$")
    text: str
    score: float


# --------------------------------------------------------- step 3: verification

class Verdict(str, Enum):
    SUPPORTED = "Supported"
    PARTIAL = "Partial"
    UNSUPPORTED = "Unsupported"
    CONTRADICTED = "Contradicted"


class ClaimVerification(BaseModel):
    """LLM-side verdict for a single claim."""

    claim_id: str = Field(pattern=r"^C\d+$")
    verdict: Verdict
    rationale: str = ""
    evidence_paragraphs: list[str] = Field(
        default_factory=list,
        description="Subset of the retrieved paragraph IDs that drove the verdict.",
    )


# --------------------------------------------------------------- step 4: report

class VerdictCounts(BaseModel):
    supported: int = 0
    partial: int = 0
    unsupported: int = 0
    contradicted: int = 0

    @property
    def total(self) -> int:
        return self.supported + self.partial + self.unsupported + self.contradicted


class EvaluationReport(BaseModel):
    """Final deliverable for one (summary, paper) pair."""

    arxiv_id: str | None = None
    title: str = ""
    paper_paragraph_count: int

    # Step 1–4 trail
    total_claims: int
    counts: VerdictCounts

    # Headline metrics — these are what the paper reports.
    evidence_coverage: float = Field(
        description=(
            "Fraction of claims supported by the paper. With config "
            "scoring.partial_credit=p, computed as "
            "(supported + p × partial) / total_claims. Higher is better."
        ),
    )
    hallucination_rate: float = Field(
        description=(
            "Fraction of claims not grounded in the paper. By default = "
            "(unsupported + contradicted) / total_claims. If "
            "scoring.unsupported_is_hallucination=false, only "
            "contradicted / total_claims. Lower is better."
        ),
    )

    # Per-claim trail (kept for paper appendix / debugging)
    per_claim: list[ClaimVerification] = Field(default_factory=list)

    # Provenance — important for reproducibility in the paper.
    eval_config: dict = Field(
        default_factory=dict,
        description="Snapshot of which extractor/verifier model + retrieval params were used.",
    )
    timestamp: str = ""
