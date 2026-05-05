from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas import (
    Claim,
    ClaimVerification,
    EvidenceChunk,
    PaperBundle,
    PaperParagraph,
    Verdict,
    VerdictCounts,
)


def test_claim_id_pattern():
    Claim(id="C1", text="x")
    with pytest.raises(ValidationError):
        Claim(id="X1", text="x")


def test_evidence_chunk_pid_pattern():
    EvidenceChunk(paragraph_id="P3", text="t", score=1.0)
    with pytest.raises(ValidationError):
        EvidenceChunk(paragraph_id="3", text="t", score=1.0)


def test_paper_bundle_lookup():
    pb = PaperBundle(paragraphs=[PaperParagraph(id="P1", text="x")])
    assert len(pb.paragraphs) == 1


def test_verdict_enum():
    cv = ClaimVerification(claim_id="C1", verdict="Supported")
    assert cv.verdict == Verdict.SUPPORTED
    # Bad enum
    with pytest.raises(ValidationError):
        ClaimVerification(claim_id="C1", verdict="Maybe")


def test_verdict_counts_total():
    c = VerdictCounts(supported=2, partial=1, unsupported=3, contradicted=1)
    assert c.total == 7
