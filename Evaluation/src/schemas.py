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


class PaperClaim(BaseModel):
    """An atomic claim extracted from the source PAPER (not the summary).

    Used for the strict-mode recall metric: for each paper claim we ask
    "did the summary cover this?". Covered/total = recall.
    """

    id: str = Field(pattern=r"^PC\d+$")
    text: str
    source_paragraph_id: str | None = Field(
        default=None,
        description="Which paragraph the claim was extracted from, e.g. 'P12'.",
    )


class PaperClaimList(BaseModel):
    """LLM-facing wrapper for paper-side claim extraction."""

    claims: list[PaperClaim] = Field(default_factory=list)


class CoverageVerdict(str, Enum):
    """Whether a paper claim was covered by the summary."""

    COVERED = "Covered"
    PARTIAL = "Partial"
    NOT_COVERED = "NotCovered"


class PaperClaimCoverage(BaseModel):
    """Per-paper-claim recall verdict."""

    claim_id: str = Field(pattern=r"^PC\d+$")
    verdict: CoverageVerdict
    rationale: str = ""


class PaperCoverageList(BaseModel):
    """LLM-facing wrapper for the recall checker."""

    items: list[PaperClaimCoverage] = Field(default_factory=list)


class CoverageCounts(BaseModel):
    covered: int = 0
    partial: int = 0
    not_covered: int = 0

    @property
    def total(self) -> int:
        return self.covered + self.partial + self.not_covered


class EvaluationReport(BaseModel):
    """Final deliverable for one (summary, paper) pair.

    Loose-mode fields (always populated):
      - total_claims, counts, evidence_coverage, hallucination_rate, per_claim

    Strict-mode fields (only populated when strict_mode=True in the config):
      - paper_total_claims, paper_coverage_counts, paper_recall, f1, per_paper_claim
    """

    arxiv_id: str | None = None
    title: str = ""
    paper_paragraph_count: int

    # ----- Loose mode (summary-side precision)
    total_claims: int
    counts: VerdictCounts
    evidence_coverage: float = Field(
        description=(
            "Loose precision: supported_summary_claims / total_summary_claims. "
            "With scoring.partial_credit=p: (supported + p × partial) / total. "
            "Penalises hallucinations but NOT under-coverage — a summary with "
            "5 trivial claims can score 1.0. Pair with `paper_recall` to "
            "guard against that."
        ),
    )
    hallucination_rate: float = Field(
        description=(
            "Fraction of summary claims not grounded in the paper. "
            "(unsupported + contradicted) / total_summary_claims. "
            "Lower is better."
        ),
    )
    per_claim: list[ClaimVerification] = Field(default_factory=list)

    # ----- Strict mode (paper-side recall + F1) — only filled when strict_mode=True
    paper_total_claims: int = 0
    paper_coverage_counts: CoverageCounts = Field(default_factory=CoverageCounts)
    paper_recall: float = Field(
        default=0.0,
        description=(
            "Strict recall: fraction of atomic claims in the PAPER that are "
            "covered by the summary. "
            "(covered + partial_credit × partial) / total_paper_claims. "
            "Penalises under-coverage. Higher is better."
        ),
    )
    f1: float = Field(
        default=0.0,
        description=(
            "Harmonic mean of evidence_coverage (precision) and paper_recall. "
            "This is the headline strict-mode metric. Higher is better."
        ),
    )
    f_half: float = Field(
        default=0.0,
        description=(
            "F-beta with beta=0.5 — precision is weighted 4× more than recall. "
            "This metric penalises missing facts LESS aggressively than F1 "
            "and is reported alongside F1 because the absolute paper_recall "
            "ceiling is bounded by summary length (a 1000-word summary can "
            "physically cover ~25 atomic claims; if a paper has 40 paper "
            "claims, perfect recall is unreachable). Use F0.5 to compare "
            "FACTUALITY across methods at fixed length budget; use F1 when "
            "you need a balanced view."
        ),
    )
    f_two: float = Field(
        default=0.0,
        description=(
            "F-beta with beta=2 — recall weighted 4× more than precision. "
            "Reported for completeness so reviewers can read off the "
            "recall-favoured number directly."
        ),
    )
    per_paper_claim: list[PaperClaimCoverage] = Field(default_factory=list)
    strict_mode: bool = False

    # Provenance — important for reproducibility in the paper.
    eval_config: dict = Field(
        default_factory=dict,
        description="Snapshot of which extractor/verifier model + retrieval params were used.",
    )
    timestamp: str = ""
