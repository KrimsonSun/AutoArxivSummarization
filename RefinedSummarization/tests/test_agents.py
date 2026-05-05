"""Agent unit tests with mocked LLM clients (handoff §9.3).

Each agent is exercised with an AsyncMock-backed LLMClient that returns
controlled fixtures, so we test the agent's transformation logic without
real API calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agents import (
    EvidenceRetrieverAgent,
    InitialSummarizerAgent,
    RefinerAgent,
    RefinerOutput,
    VerifierAgent,
)
from src.schemas.evidence import EvidenceSelection, EvidenceSelectionList
from src.schemas.issue import Issue, IssueList, IssueType
from src.schemas.paper import Paragraph, ParsedPaper
from src.schemas.summary import (
    Contribution,
    ExperimentsBlock,
    InitialSummary,
    MethodBlock,
)


def _paper(n: int = 5) -> ParsedPaper:
    return ParsedPaper(
        title="t",
        abstract="abstract " * 10,
        paragraphs=[
            Paragraph(id=f"P{i}", section="Method", text="word " * 30, summary_short="s")
            for i in range(1, n + 1)
        ],
    )


def _summary(agent_id: str = "agent_a") -> InitialSummary:
    return InitialSummary(
        agent_id=agent_id,
        tldr="t",
        core_idea="c",
        method=MethodBlock(overview="o"),
        experiments=ExperimentsBlock(setup="s"),
    )


@pytest.mark.asyncio
async def test_initial_summarizer_forces_agent_id():
    client = AsyncMock()
    client.generate.return_value = _summary("wrong_id")
    agent = InitialSummarizerAgent(client=client, agent_id="agent_correct")
    out = await agent.run(_paper())
    assert out.agent_id == "agent_correct"
    client.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_verifier_caps_at_12_issues():
    issues = [
        Issue(
            id=f"I{i}",
            type=IssueType.AMBIGUITY,
            description="d",
            affected_field="method.overview",
            claim_text="c",
        )
        for i in range(1, 20)
    ]
    client = AsyncMock()
    client.generate.return_value = IssueList(issues=issues)
    agent = VerifierAgent(client=client)
    out = await agent.run(_paper(), [_summary("a"), _summary("b"), _summary("c")])
    assert len(out) == 12, f"expected 12, got {len(out)}"


@pytest.mark.asyncio
async def test_verifier_zero_issues_pass_through():
    client = AsyncMock()
    client.generate.return_value = IssueList(issues=[])
    out = await VerifierAgent(client=client).run(
        _paper(), [_summary("a"), _summary("b"), _summary("c")]
    )
    assert out == []


@pytest.mark.asyncio
async def test_retriever_drops_unknown_paragraphs():
    """LLM hallucination guard: paragraph IDs not in the paper are skipped."""
    client = AsyncMock()
    client.generate.return_value = EvidenceSelectionList(
        selections=[
            EvidenceSelection(paragraph_id="P2", relevance_explanation="r1"),
            EvidenceSelection(paragraph_id="P99", relevance_explanation="hallucinated"),
            EvidenceSelection(paragraph_id="P3", relevance_explanation="r2"),
            EvidenceSelection(paragraph_id="P4", relevance_explanation="extra"),
        ]
    )
    issue = Issue(
        id="I1", type=IssueType.MISSING_INFO, description="d",
        affected_field="method.overview", claim_text="c"
    )
    bundle = await EvidenceRetrieverAgent(client=client).run(issue, _paper(n=5))
    pids = [e.paragraph_id for e in bundle.evidence]
    assert "P99" not in pids
    assert len(bundle.evidence) <= 3  # MAX_EVIDENCE_PER_ISSUE
    # Each evidence text must come from the paper, not the LLM
    paper = _paper(n=5)
    for e in bundle.evidence:
        assert e.text == paper.paragraph_by_id(e.paragraph_id).text


@pytest.mark.asyncio
async def test_retriever_handles_llm_failure_gracefully():
    """Retriever must NOT crash the pipeline on LLM errors (handoff §8)."""
    client = AsyncMock()
    client.generate.side_effect = RuntimeError("upstream 500")
    issue = Issue(
        id="I1", type=IssueType.MISSING_INFO, description="d",
        affected_field="method.overview", claim_text="c"
    )
    bundle = await EvidenceRetrieverAgent(client=client).run(issue, _paper())
    assert bundle.issue_id == "I1"
    assert bundle.evidence == []


@pytest.mark.asyncio
async def test_refiner_passes_through_no_evidence():
    """Refiner must work even when evidence_bundles is empty."""
    client = AsyncMock()
    client.generate.return_value = RefinerOutput(
        tldr="final tldr",
        core_idea="final core",
        key_contributions=[Contribution(text="k")],
        method=MethodBlock(overview="o"),
        experiments=ExperimentsBlock(setup="s"),
        limitations=[],
        issues_addressed=[],
    )
    out = await RefinerAgent(client=client).run(
        paper=_paper(),
        summaries=[_summary("a"), _summary("b"), _summary("c")],
        issues=[],
        evidence_bundles=[],
    )
    assert out.tldr == "final tldr"
