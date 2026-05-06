"""Step 4 — Aggregate verdicts into the headline metrics.

Loose mode (always computed):
  Evidence Coverage = (# Supported + partial_credit × # Partial) / total_summary_claims
  Hallucination Rate = (# Unsupported + # Contradicted) / total_summary_claims

Strict mode (when scoring.strict_mode=True):
  Paper Recall = (# Covered + partial_credit × # Partial) / total_paper_claims
  F1 = 2 × precision × recall / (precision + recall)
"""
from __future__ import annotations

from src.config_loader import ScoringSpec
from src.schemas import (
    ClaimVerification,
    CoverageCounts,
    CoverageVerdict,
    EvaluationReport,
    PaperClaimCoverage,
    Verdict,
    VerdictCounts,
)


def score(
    verifications: list[ClaimVerification],
    spec: ScoringSpec,
) -> tuple[VerdictCounts, float, float]:
    """Loose-mode score — summary-side precision + hallucination."""
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


def score_recall(
    coverages: list[PaperClaimCoverage],
    spec: ScoringSpec,
) -> tuple[CoverageCounts, float]:
    """Strict-mode score — paper-side recall."""
    counts = CoverageCounts()
    for c in coverages:
        if c.verdict == CoverageVerdict.COVERED:
            counts.covered += 1
        elif c.verdict == CoverageVerdict.PARTIAL:
            counts.partial += 1
        elif c.verdict == CoverageVerdict.NOT_COVERED:
            counts.not_covered += 1
    total = counts.total
    if total == 0:
        return counts, 0.0
    recall = (counts.covered + spec.partial_credit * counts.partial) / total
    return counts, recall


def f1_of(precision: float, recall: float) -> float:
    if precision + recall <= 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def fbeta_of(precision: float, recall: float, beta: float) -> float:
    """General F-beta. beta=1 is F1; beta=0.5 weights precision; beta=2 weights recall."""
    if precision <= 0 and recall <= 0:
        return 0.0
    b2 = beta * beta
    denom = b2 * precision + recall
    if denom <= 0:
        return 0.0
    return (1.0 + b2) * precision * recall / denom


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
    # --- strict mode (optional) ---
    paper_total_claims: int = 0,
    paper_coverage_counts: CoverageCounts | None = None,
    paper_recall: float = 0.0,
    f1: float = 0.0,
    per_paper_claim: list[PaperClaimCoverage] | None = None,
    strict_mode: bool = False,
) -> EvaluationReport:
    f_half = fbeta_of(coverage, paper_recall, beta=0.5) if strict_mode else 0.0
    f_two = fbeta_of(coverage, paper_recall, beta=2.0) if strict_mode else 0.0
    return EvaluationReport(
        arxiv_id=arxiv_id,
        title=title,
        paper_paragraph_count=paper_paragraph_count,
        total_claims=counts.total,
        counts=counts,
        evidence_coverage=coverage,
        hallucination_rate=hallucination,
        per_claim=verifications,
        paper_total_claims=paper_total_claims,
        paper_coverage_counts=paper_coverage_counts or CoverageCounts(),
        paper_recall=paper_recall,
        f1=f1,
        f_half=f_half,
        f_two=f_two,
        per_paper_claim=per_paper_claim or [],
        strict_mode=strict_mode,
        eval_config=config_snapshot,
        timestamp=timestamp,
    )
