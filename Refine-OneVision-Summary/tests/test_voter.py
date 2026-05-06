"""Unit tests for GameTheoryVoter — no LLM calls."""
from __future__ import annotations

import pytest

from src.agents.voter import GameTheoryVoter, VoterClient
from src.schemas.summary import (
    ExperimentsBlock,
    InitialSummary,
    MethodBlock,
)
from src.schemas.vote import DraftScore, RankingResult, VoteList


def _stub_summary(agent_id: str) -> InitialSummary:
    return InitialSummary(
        agent_id=agent_id,
        tldr=f"tldr from {agent_id}",
        core_idea=f"core from {agent_id}",
        key_contributions=[],
        method=MethodBlock(overview=f"overview {agent_id}", components=[]),
        experiments=ExperimentsBlock(setup=f"setup {agent_id}", key_findings=[]),
        limitations=[],
    )


class _FakeClient:
    """Minimal LLMClient stand-in. Returns a pre-canned VoteList."""

    def __init__(self, model_id: str, response: VoteList | Exception):
        self.model_id = model_id
        self._response = response

    async def generate(self, **kwargs):
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def healthcheck(self) -> bool:
        return True


def _vote(d1_rank, d2_rank, d3_rank, voter_id="voter") -> VoteList:
    return VoteList(scores=[
        DraftScore(draft_label="D1", rank=d1_rank, faithfulness_0_10=8, coverage_0_10=8,
                   specificity_0_10=8, fluency_0_10=8, rationale=f"r1 from {voter_id}"),
        DraftScore(draft_label="D2", rank=d2_rank, faithfulness_0_10=7, coverage_0_10=7,
                   specificity_0_10=7, fluency_0_10=7, rationale=f"r2 from {voter_id}"),
        DraftScore(draft_label="D3", rank=d3_rank, faithfulness_0_10=6, coverage_0_10=6,
                   specificity_0_10=6, fluency_0_10=6, rationale=f"r3 from {voter_id}"),
    ])


@pytest.mark.asyncio
async def test_borda_winner_is_unanimous_top():
    """All voters rank D1 first → D1 should win Borda."""
    drafts = [_stub_summary("A"), _stub_summary("B"), _stub_summary("C")]
    voters = [
        VoterClient(agent_id="A", client=_FakeClient("m1", _vote(1, 2, 3))),
        VoterClient(agent_id="B", client=_FakeClient("m2", _vote(1, 2, 3))),
        VoterClient(agent_id="C", client=_FakeClient("m3", _vote(1, 2, 3))),
    ]
    voter = GameTheoryVoter(voters=voters, rounds=3, seed=0)
    transcript = await voter.run(drafts)
    # Each voter × each round: D1=3, D2=2, D3=1. 3 voters × 3 rounds → D1=27, D2=18, D3=9.
    assert transcript.per_label_borda["D1"] == 27.0
    assert transcript.per_label_borda["D2"] == 18.0
    assert transcript.per_label_borda["D3"] == 9.0
    assert transcript.winner_label == "D1"
    # Anonymisation: which agent_id ended up at D1 depends on the seed shuffle.
    assert transcript.winner_agent_id in {"A", "B", "C"}


@pytest.mark.asyncio
async def test_abstention_excluded_from_borda():
    drafts = [_stub_summary("A"), _stub_summary("B"), _stub_summary("C")]
    # Voter A always errors; B and C vote D2 first.
    voters = [
        VoterClient(agent_id="A", client=_FakeClient("m1",
            __import__("src.llm_clients.base", fromlist=["LLMError"]).LLMError("fake"))),
        VoterClient(agent_id="B", client=_FakeClient("m2", _vote(2, 1, 3))),
        VoterClient(agent_id="C", client=_FakeClient("m3", _vote(2, 1, 3))),
    ]
    voter = GameTheoryVoter(voters=voters, rounds=3, seed=0)
    transcript = await voter.run(drafts)
    # Only B + C count; 2 voters × 3 rounds = 6 ballots. D2 = 6×3 = 18, D1 = 6×2 = 12, D3 = 6×1 = 6.
    assert transcript.per_label_borda["D2"] == 18.0
    assert transcript.per_label_borda["D1"] == 12.0
    assert transcript.per_label_borda["D3"] == 6.0
    assert transcript.winner_label == "D2"
    # Voter A's rounds should be marked as abstentions in the transcript.
    for round_results in transcript.rounds:
        a_rankings = [r for r in round_results if r.voter_id == "A"]
        assert all(r.is_abstention for r in a_rankings)


@pytest.mark.asyncio
async def test_invalid_ranks_get_coerced():
    """Voter that returns ranks [1,1,1] (all tied) should get sorted by score sum."""
    drafts = [_stub_summary("A"), _stub_summary("B"), _stub_summary("C")]
    bad_vote = VoteList(scores=[
        DraftScore(draft_label="D1", rank=1, faithfulness_0_10=5, coverage_0_10=5,
                   specificity_0_10=5, fluency_0_10=5, rationale="x"),
        DraftScore(draft_label="D2", rank=1, faithfulness_0_10=9, coverage_0_10=9,
                   specificity_0_10=9, fluency_0_10=9, rationale="x"),
        DraftScore(draft_label="D3", rank=1, faithfulness_0_10=7, coverage_0_10=7,
                   specificity_0_10=7, fluency_0_10=7, rationale="x"),
    ])
    voters = [
        VoterClient(agent_id=f"V{i}", client=_FakeClient("m", bad_vote))
        for i in range(3)
    ]
    voter = GameTheoryVoter(voters=voters, rounds=1, seed=0)
    transcript = await voter.run(drafts)
    # After coercion, D2 (score sum 36) should be rank 1; D3 (28) rank 2; D1 (20) rank 3.
    assert transcript.winner_label == "D2"
