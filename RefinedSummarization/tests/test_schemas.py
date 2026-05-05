"""Schema happy-path + boundary tests (handoff §9.2)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.evidence import EvidenceBundle, EvidenceItem, EvidenceSelection
from src.schemas.issue import Issue, IssueList, IssueType
from src.schemas.paper import Paragraph, ParsedPaper
from src.schemas.summary import (
    Contribution,
    ExperimentsBlock,
    FinalSummary,
    FinalSummaryMetadata,
    InitialSummary,
    MethodBlock,
)


def test_paragraph_valid_id():
    p = Paragraph(id="P12", section="Method", text="word " * 30)
    assert p.id == "P12"


def test_paragraph_rejects_bad_id():
    with pytest.raises(ValidationError):
        Paragraph(id="X1", section="Method", text="x")


def test_parsed_paper_lookup():
    pp = ParsedPaper(
        title="t",
        abstract="a",
        paragraphs=[
            Paragraph(id="P1", section="Abstract", text="x"),
            Paragraph(id="P2", section="Method", text="y"),
        ],
    )
    assert pp.paragraph_by_id("P2") is not None
    assert pp.paragraph_by_id("P99") is None


def test_initial_summary_minimal():
    s = InitialSummary(
        agent_id="agent_a",
        tldr="t",
        core_idea="c",
        method=MethodBlock(overview="o"),
        experiments=ExperimentsBlock(setup="s"),
    )
    assert s.agent_id == "agent_a"
    assert s.method.components == []
    assert s.limitations == []


def test_issue_enum_round_trip():
    i = Issue(
        id="I1",
        type="factual_error",
        description="d",
        affected_field="method.overview",
        claim_text="claim",
    )
    assert i.type == IssueType.FACTUAL_ERROR
    j = Issue.model_validate_json(i.model_dump_json())
    assert j.type == IssueType.FACTUAL_ERROR


def test_issue_list_empty():
    il = IssueList()
    assert il.issues == []


def test_evidence_item_paragraph_id_pattern():
    EvidenceItem(paragraph_id="P5", text="t", relevance_explanation="r")
    with pytest.raises(ValidationError):
        EvidenceItem(paragraph_id="X5", text="t", relevance_explanation="r")


def test_evidence_bundle_default_empty():
    eb = EvidenceBundle(issue_id="I1")
    assert eb.evidence == []


def test_evidence_selection_pattern():
    EvidenceSelection(paragraph_id="P1", relevance_explanation="r")
    with pytest.raises(ValidationError):
        EvidenceSelection(paragraph_id="1", relevance_explanation="r")


def test_final_summary_full():
    fs = FinalSummary(
        tldr="t",
        core_idea="c",
        key_contributions=[Contribution(text="k")],
        method=MethodBlock(overview="o"),
        experiments=ExperimentsBlock(setup="s"),
        limitations=["l"],
        metadata=FinalSummaryMetadata(
            title="t",
            paper_paragraph_count=10,
            initial_agents=["a"],
            pipeline_llm="openai:gpt-4o",
            timestamp="2025-01-01T00:00:00Z",
        ),
    )
    assert fs.metadata.total_tokens_used == {"prompt": 0, "completion": 0}
