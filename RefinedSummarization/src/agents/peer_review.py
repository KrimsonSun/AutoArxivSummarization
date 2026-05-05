"""Mutual peer-review verifier (HANDOFF §1.2 future-work hook, now realised).

Architecture:
    The same 3 heterogeneous LLMs that produced the initial draft summaries
    ALSO independently critique all three drafts. Each reviewer outputs an
    IssueList of up to MAX_ISSUES_PER_REVIEWER issues. The aggregator then:

    1. Tags every issue with the reviewer that raised it (``raised_by``).
    2. Deduplicates near-identical issues across reviewers, merging their
       ``raised_by`` lists. Two issues are considered "the same" iff they
       share (issue_type, normalised affected_field). This is conservative
       — semantic duplicates with different field paths survive as separate
       issues, which is fine because the refiner can still see them.
    3. Sorts issues by:
            primary   — # of reviewers that raised it (consensus, descending)
            secondary — average rank within source list (severity proxy)
       so that highest-consensus / highest-severity issues come first.
    4. Caps at GLOBAL_MAX_ISSUES (12, matching HANDOFF §2.3) and re-IDs
       sequentially I1, I2, ...

The point of this design (vs. a single judge) is to surface BOTH:
    -  Cross-model consensus issues (3 reviewers all flag a missing dataset
       detail → very likely real)
    -  Single-model unique perspective issues (only Claude flags a method
       ambiguity → keep it; might be a real flaw GPT/Gemini missed)

Both signals are encoded in the ``raised_by`` field, which the refiner
prompt surfaces so the integrator can weight consensus issues higher.
"""
from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from typing import Iterable

from src.agents.verifier import VerifierAgent
from src.llm_clients.base import LLMClient, LLMError
from src.schemas.issue import Issue
from src.schemas.paper import ParsedPaper
from src.schemas.summary import InitialSummary
from src.utils.logging import get_logger

# Each reviewer is asked for up to this many; the global cap below applies
# AFTER aggregation. Set lower than the global cap so 3 reviewers don't all
# saturate to 12 each (=> 36 raw issues which would make aggregation noisy).
MAX_ISSUES_PER_REVIEWER = 8

# Final list size handed to retriever + refiner. Same as HANDOFF §2.3.
GLOBAL_MAX_ISSUES = 12

_log = get_logger("peer_review")


class PeerReviewVerifier:
    """Drop-in replacement for VerifierAgent that runs N heterogeneous reviewers."""

    def __init__(self, reviewer_clients: list[tuple[str, LLMClient]]):
        if len(reviewer_clients) < 2:
            raise ValueError(
                f"PeerReviewVerifier needs ≥ 2 reviewers, got {len(reviewer_clients)}"
            )
        # Each (reviewer_id, VerifierAgent) — the VerifierAgent prompt already
        # frames the LLM as a peer reviewer evaluating three drafts; reusing
        # it keeps the contract consistent across modes.
        self.reviewers: list[tuple[str, VerifierAgent]] = [
            (rid, VerifierAgent(client=c)) for rid, c in reviewer_clients
        ]

    async def run(
        self,
        paper: ParsedPaper,
        summaries: list[InitialSummary],
    ) -> list[Issue]:
        """Run all reviewers in parallel, then aggregate into a single list."""
        per_reviewer_issues = await asyncio.gather(
            *[
                self._safe_review(rid, agent, paper, summaries)
                for rid, agent in self.reviewers
            ]
        )
        # per_reviewer_issues: list[(reviewer_id, list[Issue])]
        if not any(lst for _, lst in per_reviewer_issues):
            _log.info("peer_review_no_issues")
            return []

        tagged = self._tag_with_reviewer(per_reviewer_issues)
        merged = self._dedupe_and_merge(tagged)
        ranked = self._rank(merged)
        capped = ranked[:GLOBAL_MAX_ISSUES]
        renumbered = self._renumber(capped)

        _log.info(
            "peer_review_aggregated",
            per_reviewer={rid: len(lst) for rid, lst in per_reviewer_issues},
            after_dedupe=len(merged),
            kept=len(renumbered),
            consensus_2plus=sum(1 for i in renumbered if len(i.raised_by) >= 2),
            consensus_3plus=sum(1 for i in renumbered if len(i.raised_by) >= 3),
        )
        return renumbered

    # ------------------------------------------------------------------ helpers

    async def _safe_review(
        self,
        rid: str,
        agent: VerifierAgent,
        paper: ParsedPaper,
        summaries: list[InitialSummary],
    ) -> tuple[str, list[Issue]]:
        """One reviewer's pass. Failures degrade to an empty list — we
        prefer running on 2 reviewers than crashing the whole pipeline."""
        try:
            issues = await agent.run(paper, summaries)
            issues = issues[:MAX_ISSUES_PER_REVIEWER]
            return rid, issues
        except LLMError as e:
            _log.warning("peer_reviewer_failed", reviewer=rid, err=str(e))
            return rid, []

    def _tag_with_reviewer(
        self,
        per_reviewer: Iterable[tuple[str, list[Issue]]],
    ) -> list[tuple[Issue, int]]:
        """Annotate each issue with the reviewer that raised it. Returns a
        list of (issue, original_rank) pairs so we can use rank for severity."""
        out: list[tuple[Issue, int]] = []
        for rid, issues in per_reviewer:
            for rank, issue in enumerate(issues):
                # Attach this single reviewer; will be merged below.
                issue.raised_by = [rid]
                out.append((issue, rank))
        return out

    def _dedupe_and_merge(
        self,
        tagged: list[tuple[Issue, int]],
    ) -> list[tuple[Issue, list[int]]]:
        """Merge issues that share the same (type, normalised affected_field).

        The merged issue keeps the longest description (most informative),
        the union of suggested_paragraphs, the union of raised_by, and the
        list of original ranks (used for severity scoring).
        """
        groups: dict[tuple[str, str], list[tuple[Issue, int]]] = defaultdict(list)
        for issue, rank in tagged:
            key = (issue.type.value, _normalise_field(issue.affected_field))
            groups[key].append((issue, rank))

        merged: list[tuple[Issue, list[int]]] = []
        for _, items in groups.items():
            if len(items) == 1:
                issue, rank = items[0]
                merged.append((issue, [rank]))
                continue
            # Merge multi-reviewer hits.
            issues_in_group = [i for i, _ in items]
            ranks_in_group = [r for _, r in items]
            base = max(issues_in_group, key=lambda i: len(i.description or ""))
            base.raised_by = sorted(
                {rid for issue in issues_in_group for rid in issue.raised_by}
            )
            base.affected_summaries = sorted(
                {a for issue in issues_in_group for a in issue.affected_summaries}
            )
            base.suggested_paragraphs = sorted(
                {p for issue in issues_in_group for p in issue.suggested_paragraphs}
            )
            merged.append((base, ranks_in_group))
        return merged

    def _rank(
        self,
        merged: list[tuple[Issue, list[int]]],
    ) -> list[Issue]:
        """Sort by consensus (desc), then by avg severity rank (asc)."""
        def key(item: tuple[Issue, list[int]]) -> tuple[int, float]:
            issue, ranks = item
            consensus = -len(issue.raised_by)  # negative for descending
            avg_rank = sum(ranks) / len(ranks) if ranks else 0.0
            return (consensus, avg_rank)
        return [issue for issue, _ in sorted(merged, key=key)]

    def _renumber(self, issues: list[Issue]) -> list[Issue]:
        for new_idx, issue in enumerate(issues, start=1):
            issue.id = f"I{new_idx}"
        return issues


# ----------------------------------------------------------- module-private utils

_BRACKET_INDEX = re.compile(r"\[\d+\]")


def _normalise_field(field: str) -> str:
    """Strip array indices so 'key_contributions[2]' and 'key_contributions[3]'
    aren't treated as wholly distinct fields."""
    return _BRACKET_INDEX.sub("[]", field).lower().strip()
