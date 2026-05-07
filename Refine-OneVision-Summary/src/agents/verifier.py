"""Single-draft verifier (Refine-OneVision Stage 3).

Difference from the v1 RefinedSummarization VerifierAgent:

  v1:  - Inputs: paper + 3 drafts; flags cross-draft inconsistencies.
       - Sees paper paragraph SHORT SUMMARIES only (lossy).
  this: - Inputs: paper + ONE winning draft (Stage 2 output).
        - Sees FULL paragraph TEXT — fixes the v1 bug where specific
          numbers/names were filtered out by paragraph_summarizer
          before the verifier could check them.

Issue types raised here are a subset of the v1 schema since "inconsistency"
and "coverage_gap" don't apply to a single-source draft:

  - factual_error      — claim contradicts paper
  - missing_info       — important paper fact absent from draft
  - unsupported_claim  — claim has no evidence_refs and isn't obvious
  - ambiguity          — claim is too vague to verify

The refiner uses these to insert / correct facts in the winning draft.
"""
from __future__ import annotations

from src.agents._prompts import render, schema_example_block
from src.llm_clients.base import LLMClient
from src.schemas.issue import Issue, IssueList
from src.schemas.paper import ParsedPaper
from src.schemas.summary import InitialSummary

MAX_ISSUES = 12


class SingleDraftVerifierAgent:
    """One LLM call:  (paper full text + winning draft) → IssueList."""

    def __init__(self, client: LLMClient):
        self.client = client

    async def run(
        self,
        paper: ParsedPaper,
        winning_draft: InitialSummary,
    ) -> list[Issue]:
        system = (
            render("verifier_onevision", "system")
            + "\n\n"
            + schema_example_block(IssueList)
        )
        user = render(
            "verifier_onevision", "user",
            paper=paper,
            draft=winning_draft,
        )
        result: IssueList = await self.client.generate(
            system_prompt=system,
            user_prompt=user,
            response_schema=IssueList,
            temperature=0.0,
            max_tokens=8192,  # 12 issues × ~600 tokens of rationale
        )
        return list(result.issues)[:MAX_ISSUES]
