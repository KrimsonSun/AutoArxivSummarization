"""End-to-end pipeline tests.

Two flavors:
1. ``test_pipeline_with_mocked_llms`` — always runs. Replaces every LLMClient
   on the pipeline with an AsyncMock that returns canned data so we can verify
   the orchestration end-to-end (asyncio.gather of 3 summarizers, verifier
   issuing issues, retriever pulling evidence, refiner merging).

2. ``test_pipeline_real_e2e`` — only runs with ``RUN_E2E=1``. Hits real LLMs
   (small/cheap models) per handoff §9.4 acceptance test.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.agents.refiner import RefinerOutput
from src.config.loader import load_config
from src.pipeline import DebatePipeline
from src.schemas.evidence import EvidenceSelection, EvidenceSelectionList
from src.schemas.issue import Issue, IssueList, IssueType
from src.schemas.summary import (
    Contribution,
    ExperimentsBlock,
    InitialSummary,
    MethodBlock,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_paper.pdf"


def _make_initial(agent_id: str) -> InitialSummary:
    return InitialSummary(
        agent_id=agent_id,
        tldr=f"tldr from {agent_id}",
        core_idea="core idea",
        key_contributions=[
            Contribution(text=f"contribution from {agent_id}", evidence_refs=["P1"])
        ],
        method=MethodBlock(overview="overview"),
        experiments=ExperimentsBlock(setup="setup"),
        limitations=["lim"],
    )


def _make_issues() -> IssueList:
    return IssueList(
        issues=[
            Issue(
                id="I1",
                type=IssueType.MISSING_INFO,
                description="lacking dataset details",
                affected_summaries=["agent_gpt4o", "agent_claude"],
                affected_field="experiments.setup",
                claim_text="setup",
                suggested_paragraphs=[],
            ),
            Issue(
                id="I2",
                type=IssueType.UNSUPPORTED_CLAIM,
                description="contribution claim has weak evidence",
                affected_summaries=["agent_gemini"],
                affected_field="key_contributions[0]",
                claim_text="contribution from agent_gemini",
                suggested_paragraphs=["P2"],
            ),
        ]
    )


def _make_evidence_selection() -> EvidenceSelectionList:
    return EvidenceSelectionList(
        selections=[
            EvidenceSelection(paragraph_id="P1", relevance_explanation="cites methods"),
            EvidenceSelection(paragraph_id="P2", relevance_explanation="cites results"),
        ]
    )


def _make_refiner_output() -> RefinerOutput:
    return RefinerOutput(
        tldr="merged tldr",
        core_idea="merged core idea",
        key_contributions=[Contribution(text="merged contribution", evidence_refs=["P1", "P2"])],
        method=MethodBlock(overview="merged overview"),
        experiments=ExperimentsBlock(setup="merged setup"),
        limitations=["merged limitation"],
        issues_addressed=["I1", "I2"],
    )


def _wire_mock_clients(pipeline: DebatePipeline) -> None:
    """Replace every LLMClient on the pipeline with an AsyncMock that
    returns the appropriate canned response based on the schema requested."""
    from src.agents.refiner import RefinerOutput as RefSchema

    def _make_mock_client():
        client = AsyncMock()

        async def _generate(*, response_schema, **kw):
            if response_schema is InitialSummary:
                # The initial summarizer overrides agent_id post-hoc, so we
                # don't need to pre-set it correctly here.
                return _make_initial("placeholder")
            if response_schema is IssueList:
                return _make_issues()
            if response_schema is EvidenceSelectionList:
                return _make_evidence_selection()
            if response_schema is RefSchema:
                return _make_refiner_output()
            # Paragraph short-summary: the schema lives in preprocessing.
            from src.preprocessing.paragraph_summarizer import _ShortSummaryList, _ShortSummary
            if response_schema is _ShortSummaryList:
                return _ShortSummaryList(items=[
                    _ShortSummary(id="P1", summary_short="short")
                ])
            raise AssertionError(f"unexpected schema: {response_schema}")

        client.generate.side_effect = _generate
        client.healthcheck.return_value = True
        client.usage.prompt_tokens = 100
        client.usage.completion_tokens = 50
        client.usage.calls = 1
        client.model_id = "mock-model"
        return client

    # Replace on the agents
    for ag in pipeline._summarizer_agents:
        ag.client = _make_mock_client()
    pipeline._verifier.client = _make_mock_client()
    pipeline._retriever.client = _make_mock_client()
    pipeline._refiner.client = _make_mock_client()
    pipeline._paragraph_summarizer.client = _make_mock_client()
    pipeline._pipeline_client = pipeline._verifier.client
    pipeline._initial_clients = [
        (aid, ag.client) for aid, ag in zip(
            [a.agent_id for a in pipeline._summarizer_agents], pipeline._summarizer_agents
        )
    ]


@pytest.mark.asyncio
@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture pdf missing")
async def test_pipeline_with_mocked_llms():
    config = load_config("config/default.yaml")
    pipeline = DebatePipeline(config)
    _wire_mock_clients(pipeline)

    result = await pipeline.run(FIXTURE)

    # Schema is valid (Pydantic guarantees this on construction).
    assert result.tldr == "merged tldr"
    # All initial agents listed
    assert len(result.metadata.initial_agents) == 3
    # Issues raised + addressed are recorded
    assert result.metadata.issues_raised == 2
    assert set(result.metadata.issues_addressed) == {"I1", "I2"}
    # Evidence paragraph IDs come from the paper (handoff §12 invariant).
    valid_pids = {p.id for p in (await _parse_for_test(FIXTURE)).paragraphs}
    for pid in result.metadata.evidence_paragraphs_used:
        assert pid in valid_pids, f"evidence paragraph {pid} not in paper"
    # No initial agent failed in the mock case
    assert result.metadata.failed_initial_agents == []
    # token tally is non-zero (mocks set it)
    assert result.metadata.total_tokens_used["prompt"] > 0


async def _parse_for_test(path: Path):
    from src.preprocessing.pdf_parser import parse_pdf
    return parse_pdf(path)


@pytest.mark.asyncio
@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture pdf missing")
async def test_pipeline_handles_one_initial_failure():
    """If 1 of 3 initial summarizers fails, pipeline continues with 2 (handoff §8)."""
    config = load_config("config/default.yaml")
    pipeline = DebatePipeline(config)
    _wire_mock_clients(pipeline)

    # Make the first initial summarizer fail (agent ID depends on config —
    # we read it dynamically so this test stays robust to model swaps).
    from src.llm_clients.base import LLMError
    failed_id = pipeline._summarizer_agents[0].agent_id
    pipeline._summarizer_agents[0].client.generate.side_effect = LLMError("simulated fail")

    result = await pipeline.run(FIXTURE)
    assert failed_id in result.metadata.failed_initial_agents
    assert len(result.metadata.failed_initial_agents) == 1


@pytest.mark.asyncio
@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture pdf missing")
async def test_pipeline_aborts_on_two_initial_failures():
    """If 2 of 3 fail, pipeline raises PipelineError."""
    from src.llm_clients.base import LLMError
    from src.pipeline import PipelineError as PE

    config = load_config("config/default.yaml")
    pipeline = DebatePipeline(config)
    _wire_mock_clients(pipeline)

    pipeline._summarizer_agents[0].client.generate.side_effect = LLMError("fail")
    pipeline._summarizer_agents[1].client.generate.side_effect = LLMError("fail")

    with pytest.raises(PE):
        await pipeline.run(FIXTURE)


@pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="Real E2E test disabled. Set RUN_E2E=1 to enable.",
)
@pytest.mark.asyncio
async def test_pipeline_real_e2e():
    """Real LLM E2E (handoff §9.4). Requires real API keys."""
    config = load_config("config/default.yaml")
    pipeline = DebatePipeline(config)
    result = await pipeline.run(FIXTURE)
    # Acceptance invariants from handoff §12
    valid_pids = {p.id for p in (await _parse_for_test(FIXTURE)).paragraphs}
    for pid in result.metadata.evidence_paragraphs_used:
        assert pid in valid_pids
    # Issues addressed must be a subset of the issues raised.
    assert len(result.metadata.issues_addressed) <= result.metadata.issues_raised
