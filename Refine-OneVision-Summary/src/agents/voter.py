"""Game-theory voter — Stage 2 (Borda / legacy mode).

Three LLMs (the same ones that drafted) run K rounds of cross-evaluation
over the 3 drafts. Drafts are presented under anonymous labels (D1/D2/D3)
AND the JSON is serialised with `agent_id` excluded so authorship cannot
leak via the dump's first key (this leak was Bug 1 of the n=29 voter
audit — see docs/BUG_REPORT_voter_bias.md). The voter prompt also no
longer carries `voter_id`, so each voter doesn't know its own identity
(Bug 2 — self-preference). The rubric was rewritten to score
"specific facts per 100 words" rather than raw coverage so that draft
length stops biasing the vote toward the longest-by-default model
(Bug 3).

This module is retained as the legacy "borda" voting method. The
default voting method in v2 is `claim_grounding` (see
`claim_grounding_voter.py`), which replaces subjective LLM ranking with
verifier-derived issue-density scoring per the SpecEM principle —
substitute objective per-token / per-claim signals for subjective
judging.

Why this is in the pipeline at all:
  Multi-agent debate is empirically strong on consensus-reasoning tasks
  (one truth, agents converge). Selecting the best of 3 drafts IS a
  consensus-reasoning task. By contrast, merging 3 drafts is a
  union-reconstruction task, which is where v1's refiner failed.
  This module isolates the consensus-reasoning use of debate, then
  hands one good draft to a single-source refiner.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from src.agents._prompts import render, schema_example_block
from src.llm_clients.base import LLMClient, LLMError
from src.schemas.summary import InitialSummary
from src.schemas.vote import (
    DraftScore,
    RankingResult,
    VoteList,
    VotingTranscript,
)


@dataclass
class VoterClient:
    """A single LLM voter — agent_id + LLMClient."""

    agent_id: str
    client: LLMClient


class GameTheoryVoter:
    """Run K rounds of voting; return a VotingTranscript with the winner.

    Parameters
    ----------
    voters
        List of VoterClient — one per voting LLM (typically the same 3
        LLMs that produced the drafts).
    rounds
        How many voting rounds. Default 3.
    seed
        Seed for the anonymous-label permutation. Same seed across runs
        means same D1/D2/D3 mapping for reproducibility.
    """

    def __init__(
        self,
        voters: list[VoterClient],
        rounds: int = 3,
        seed: int = 42,
    ):
        if len(voters) != 3:
            raise ValueError(f"GameTheoryVoter requires exactly 3 voters; got {len(voters)}")
        self.voters = voters
        self.rounds = rounds
        self.rng = random.Random(seed)

    async def run(self, drafts: list[InitialSummary]) -> VotingTranscript:
        if len(drafts) != 3:
            raise ValueError(f"voter requires exactly 3 drafts; got {len(drafts)}")

        # ---- Anonymise drafts: D1/D2/D3 in random order ----
        labels = ["D1", "D2", "D3"]
        order = labels.copy()
        self.rng.shuffle(order)
        # order is e.g. ["D2", "D1", "D3"] — drafts[i] gets label order[i]
        label_to_agent: dict[str, str] = {
            order[i]: drafts[i].agent_id for i in range(3)
        }
        labelled_drafts: list[tuple[str, InitialSummary]] = [
            (order[i], drafts[i]) for i in range(3)
        ]
        # Sort so it's always presented D1, D2, D3 in the prompt.
        labelled_drafts.sort(key=lambda lab_d: lab_d[0])

        # ---- Run K rounds ----
        all_rounds: list[list[RankingResult]] = []
        for r in range(1, self.rounds + 1):
            round_results = await self._run_round(
                round_index=r,
                labelled_drafts=labelled_drafts,
                prior_rounds=all_rounds,
            )
            all_rounds.append(round_results)

        # ---- Aggregate Borda count ----
        per_label_borda = self._borda_totals(all_rounds)
        winner_label = max(per_label_borda, key=per_label_borda.get)
        winner_agent_id = label_to_agent[winner_label]

        return VotingTranscript(
            voter_ids=[v.agent_id for v in self.voters],
            label_to_agent=label_to_agent,
            rounds=all_rounds,
            winner_label=winner_label,
            winner_agent_id=winner_agent_id,
            winner_total_borda=per_label_borda[winner_label],
            per_label_borda=per_label_borda,
        )

    # --------------------------------------------------------- internal

    async def _run_round(
        self,
        round_index: int,
        labelled_drafts: list[tuple[str, InitialSummary]],
        prior_rounds: list[list[RankingResult]],
    ) -> list[RankingResult]:
        # All voters in parallel.
        tasks = [
            self._one_voter(
                voter=v,
                round_index=round_index,
                labelled_drafts=labelled_drafts,
                prior_rounds=prior_rounds,
            )
            for v in self.voters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Defensive: if a voter fails this round, fill with a placeholder
        # ranking that abstains (all 3 drafts ranked equally — gives 0
        # Borda differentiation for that voter this round).
        out: list[RankingResult] = []
        for v, r in zip(self.voters, results):
            if isinstance(r, Exception):
                out.append(_abstain_ranking(v.agent_id, round_index, labelled_drafts))
            else:
                out.append(r)
        return out

    async def _one_voter(
        self,
        voter: VoterClient,
        round_index: int,
        labelled_drafts: list[tuple[str, InitialSummary]],
        prior_rounds: list[list[RankingResult]],
    ) -> RankingResult:
        system = (
            render("voter", "system", round_index=round_index, total_rounds=self.rounds)
            + "\n\n"
            + schema_example_block(VoteList)
        )
        # Voter must NOT know its own identity (was Bug 2 — self-preference).
        # voter.agent_id is retained server-side only for transcript bookkeeping;
        # it is never rendered into the prompt.
        user = render(
            "voter",
            "user",
            round_index=round_index,
            labelled_drafts=labelled_drafts,
            prior_rounds=prior_rounds,
        )
        try:
            result: VoteList = await voter.client.generate(
                system_prompt=system,
                user_prompt=user,
                response_schema=VoteList,
                temperature=0.0,
                max_tokens=2048,
            )
        except LLMError:
            return _abstain_ranking(voter.agent_id, round_index, labelled_drafts)

        # Validate ranks form a permutation of {1, 2, 3}.
        ranks = sorted(s.rank for s in result.scores)
        if ranks != [1, 2, 3]:
            # Coerce: assign by overall score (sum of 4 sub-scores), break
            # ties by faithfulness then specificity then coverage.
            sorted_scores = sorted(
                result.scores,
                key=lambda s: (
                    -(s.faithfulness_0_10 + s.coverage_0_10 + s.specificity_0_10 + s.fluency_0_10),
                    -s.faithfulness_0_10,
                    -s.specificity_0_10,
                    -s.coverage_0_10,
                ),
            )
            for i, s in enumerate(sorted_scores):
                s.rank = i + 1

        return RankingResult(
            voter_id=voter.agent_id,
            round_index=round_index,
            scores=result.scores,
        )

    @staticmethod
    def _borda_totals(all_rounds: list[list[RankingResult]]) -> dict[str, float]:
        """Borda: rank 1 → 3 pts, rank 2 → 2 pts, rank 3 → 1 pt.

        Sum across all (voter, round) pairs. Abstaining rankings excluded.
        """
        totals: dict[str, float] = {"D1": 0.0, "D2": 0.0, "D3": 0.0}
        for round_results in all_rounds:
            for ranking in round_results:
                if ranking.is_abstention:
                    continue
                for s in ranking.scores:
                    totals[s.draft_label] += float(4 - s.rank)  # 1→3, 2→2, 3→1
        return totals


def _abstain_ranking(
    voter_id: str,
    round_index: int,
    labelled_drafts: list[tuple[str, InitialSummary]],
) -> RankingResult:
    """Voter call failed; produce a record but mark it as an abstention so
    Borda excludes it."""
    return RankingResult(
        voter_id=voter_id,
        round_index=round_index,
        is_abstention=True,
        scores=[
            DraftScore(
                draft_label=label,
                rank=i + 1,  # nominal placeholder; ignored by Borda
                faithfulness_0_10=5,
                coverage_0_10=5,
                specificity_0_10=5,
                fluency_0_10=5,
                rationale="Voter abstained (call failed or returned invalid output).",
            )
            for i, (label, _) in enumerate(labelled_drafts)
        ],
    )
