"""Step 4 — Aggregate verdicts into the headline metrics.

Defines two metrics per the user's spec:

  Evidence Coverage = (# Supported + partial_credit × # Partial) / total
  Hallucination Rate = (# Unsupported + # Contradicted) / total
                       (or only # Contradicted if config flag is off)

Both are in [0, 1]. Higher coverage / lower hallucination = better summary.
"""
from __future__ import annotations

from src.config_loader import ScoringSpec
from src.schemas import (
    ClaimVerification,
    EvaluationReport,
    VerdictCounts,
    Verdict,
)


def score(
    verifications: list[ClaimVerification],
    spec: ScoringSpec,
) -> tuple[VerdictCounts, float, float]:
    """Returns (counts, evidence_coverage, hallucination_rate)."""
    counts = VerdictCounts()
    for v in verifications:
        if v.verdict == Verdict.SUPPORTED:
            counts.supported += 1
        elif v.verdict == Verdict.PARTIAL:
            counts.partial += 1
        elif v.verdict == Verdict.UNSUPPORTED:
            counts.unsupported += 1
        elif v.verdict == Verdict.CONTRADICTED:
            counts.contradicted += 1
    total = counts.total
    if total == 0:
        return counts, 0.0, 0.0

    evidence_coverage = (
        counts.supported + spec.partial_credit * counts.partial
    ) / total

    if spec.unsupported_is_hallucination:
        hallucination = (counts.unsupported + counts.contradicted) / total
    else:
        hallucination = counts.contradicted / total

    return counts, evidence_coverage, hallucination


def assemble_report(
    arxiv_id: str | None,
    title: str,
    paper_paragraph_count: int,
    verifications: list[ClaimVerification],
    counts: VerdictCounts,
    coverage: float,
    hallucination: float,
    config_snapshot: dict,
    timestamp: str,
) -> EvaluationReport:
    return EvaluationReport(
        arxiv_id=arxiv_id,
        title=title,
        paper_paragraph_count=paper_paragraph_count,
        total_claims=counts.total,
        counts=counts,
        evidence_coverage=coverage,
        hallucination_rate=hallucination,
        per_claim=verifications,
        eval_config=config_snapshot,
        timestamp=timestamp,
    )
