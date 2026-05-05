"""Mocked E2E: replace LLMClient.generate with canned responses, run the full
4-step pipeline against a tiny in-memory paper, assert metrics shape + values."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.config_loader import load_config
from src.pipeline import EvaluationPipeline
from src.schemas import (
    Claim,
    ClaimList,
    ClaimVerification,
    PaperBundle,
    PaperParagraph,
    Verdict,
)


@pytest.fixture
def tiny_paper(tmp_path: Path) -> Path:
    pb = PaperBundle(
        arxiv_id="2412.07380",
        title="Test paper",
        paragraphs=[
            PaperParagraph(id="P1", text="The model achieves 28.4 BLEU on WMT 2014 EN-DE."),
            PaperParagraph(id="P2", text="It uses self-attention without recurrence."),
            PaperParagraph(id="P3", text="Training takes 3.5 days on 8 GPUs."),
        ],
    )
    p = tmp_path / "paper.json"
    p.write_text(pb.model_dump_json())
    return p


@pytest.fixture
def tiny_summary(tmp_path: Path) -> Path:
    fs = {
        "tldr": "A new attention-based model gets 28.4 BLEU on WMT 2014.",
        "core_idea": "Replace recurrence with self-attention.",
        "key_contributions": [
            {"text": "Achieves state-of-the-art BLEU.", "evidence_refs": []},
        ],
        "method": {
            "overview": "Transformer architecture.",
            "components": [],
        },
        "experiments": {"setup": "WMT 2014 corpus.", "key_findings": []},
        "limitations": [],
        "metadata": {
            "title": "Test paper",
            "paper_paragraph_count": 3,
            "initial_agents": ["a"],
            "pipeline_llm": "x",
            "timestamp": "2026-01-01T00:00:00Z",
        },
    }
    p = tmp_path / "summary.json"
    p.write_text(json.dumps(fs))
    return p


def _wire_mocks(pipeline: EvaluationPipeline) -> None:
    extracted_claims = ClaimList(claims=[
        Claim(id="C1", text="The model achieves 28.4 BLEU on WMT 2014 EN-DE.", source_field="tldr"),
        Claim(id="C2", text="It replaces recurrence with self-attention.", source_field="core_idea"),
        Claim(id="C3", text="It improves training time by 50%.", source_field="key_contributions[0]"),
    ])

    async def _generate(*, response_schema, **kw):
        if response_schema is ClaimList:
            return extracted_claims
        if response_schema is ClaimVerification:
            # Decide verdict based on the claim_id text in the user prompt.
            user = kw.get("user_prompt", "")
            if "Claim ID: C1" in user:
                return ClaimVerification(claim_id="C1", verdict=Verdict.SUPPORTED, evidence_paragraphs=["P1"])
            if "Claim ID: C2" in user:
                return ClaimVerification(claim_id="C2", verdict=Verdict.SUPPORTED, evidence_paragraphs=["P2"])
            if "Claim ID: C3" in user:
                return ClaimVerification(claim_id="C3", verdict=Verdict.UNSUPPORTED)
        raise AssertionError(f"unexpected schema {response_schema}")

    mock = AsyncMock()
    mock.generate.side_effect = _generate
    mock.healthcheck.return_value = True
    mock.usage.prompt_tokens = 100
    mock.usage.completion_tokens = 50
    mock.usage.calls = 1
    mock.model_id = "mock-model"
    pipeline._extractor.client = mock
    pipeline._verifier.client = mock
    pipeline._extractor_client = mock
    pipeline._verifier_client = mock


@pytest.mark.asyncio
async def test_pipeline_full_flow(tiny_paper, tiny_summary):
    config = load_config("config/default.yaml")
    pipeline = EvaluationPipeline(config)
    _wire_mocks(pipeline)

    report = await pipeline.run(tiny_summary, tiny_paper)

    assert report.total_claims == 3
    assert report.counts.supported == 2
    assert report.counts.unsupported == 1
    # Coverage = 2 supported + 0 partial = 2/3 ≈ 0.667
    assert report.evidence_coverage == pytest.approx(2 / 3)
    # Hallucination = 1 unsupported / 3 = 0.333
    assert report.hallucination_rate == pytest.approx(1 / 3)
    # Per-claim trail preserved
    assert len(report.per_claim) == 3
    assert report.arxiv_id == "2412.07380"


@pytest.mark.asyncio
async def test_pipeline_empty_claims(tiny_paper, tmp_path):
    """Empty summary → empty report (defensive)."""
    summary = tmp_path / "empty.txt"
    summary.write_text("")
    config = load_config("config/default.yaml")
    pipeline = EvaluationPipeline(config)

    # Mock returning zero claims
    mock = AsyncMock()
    mock.generate.return_value = ClaimList(claims=[])
    mock.healthcheck.return_value = True
    pipeline._extractor.client = mock
    pipeline._verifier.client = mock
    pipeline._extractor_client = mock
    pipeline._verifier_client = mock

    report = await pipeline.run(summary, tiny_paper)
    assert report.total_claims == 0
    assert report.evidence_coverage == 0.0
    assert report.hallucination_rate == 0.0
