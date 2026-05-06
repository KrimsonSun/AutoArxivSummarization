"""Verifier agent (handoff §2.3, §4.2)."""
from __future__ import annotations

from src.agents._prompts import render, schema_example_block
from src.llm_clients.base import LLMClient
from src.schemas.issue import Issue, IssueList
from src.schemas.paper import ParsedPaper
from src.schemas.summary import InitialSummary

# Per-call cap. In single_judge mode this is the global cap (matches HANDOFF
# §2.3). In mutual_peer_review mode the PeerReviewVerifier further caps each
# reviewer at MAX_ISSUES_PER_REVIEWER (=8) before aggregation, so this 12
# value is effectively a safety ceiling rather than the binding constraint.
MAX_ISSUES = 12


class VerifierAgent:
    def __init__(self, client: LLMClient):
        self.client = client

    async def run(
        self,
        paper: ParsedPaper,
        summaries: list[InitialSummary],
    ) -> list[Issue]:
        system = render("verifier", "system") + "\n\n" + schema_example_block(IssueList)
        user = render("verifier", "user", paper=paper, summaries=summaries)
        result: IssueList = await self.client.generate(
            system_prompt=system,
            user_prompt=user,
            response_schema=IssueList,
            temperature=0.3,
            max_tokens=4096,
        )
        # Truncate to the contractual maximum (handoff §2.3).
        return list(result.issues)[:MAX_ISSUES]
