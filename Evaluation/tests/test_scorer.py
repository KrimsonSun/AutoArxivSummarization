from __future__ import annotations

import pytest

from src.config_loader import ScoringSpec
from src.schemas import ClaimVerification, Verdict
from src.scorer import score


def _v(claim_id: str, verdict: Verdict) -> ClaimVerification:
    return ClaimVerification(claim_id=claim_id, verdict=verdict)


def test_all_supported():
    vs = [_v(f"C{i}", Verdict.SUPPORTED) for i in range(1, 5)]
    counts, cov, hall = score(vs, ScoringSpec())
    assert counts.supported == 4
    assert cov == 1.0
    assert hall == 0.0


def test_all_unsupported_default_counts_as_hallucination():
    vs = [_v(f"C{i}", Verdict.UNSUPPORTED) for i in range(1, 4)]
    counts, cov, hall = score(vs, ScoringSpec())
    assert cov == 0.0
    assert hall == 1.0


def test_partial_credit_default_half():
    vs = [
        _v("C1", Verdict.SUPPORTED),
        _v("C2", Verdict.PARTIAL),
        _v("C3", Verdict.UNSUPPORTED),
        _v("C4", Verdict.CONTRADICTED),
    ]
    counts, cov, hall = score(vs, ScoringSpec(partial_credit=0.5))
    assert cov == pytest.approx((1 + 0.5) / 4)
    assert hall == pytest.approx(2 / 4)


def test_unsupported_not_hallucination_when_disabled():
    vs = [
        _v("C1", Verdict.UNSUPPORTED),
        _v("C2", Verdict.UNSUPPORTED),
        _v("C3", Verdict.CONTRADICTED),
    ]
    spec = ScoringSpec(unsupported_is_hallucination=False)
    _, _, hall = score(vs, spec)
    assert hall == pytest.approx(1 / 3)  # only 1 contradicted


def test_empty_input():
    counts, cov, hall = score([], ScoringSpec())
    assert counts.total == 0
    assert cov == 0.0 and hall == 0.0
