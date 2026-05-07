"""Single-draft refiner (Refine-OneVision Stage 5).

Difference from the v1 RefinedSummarization RefinerAgent:

  v1:  - Inputs: paper + 3 drafts + issues + evidence.
       - Job: MERGE 3 drafts into one. This is the failure point — the
         refiner intersects rather than unions, dropping draft-only
         specifics.
  this: - Inputs: paper + ONE winning draft + issues + evidence.
        - Job: AUGMENT the winning draft with missing facts and correct
          distorted ones, using only the supplied evidence. NO merge.

The output schema (`RefinerOutput`) is unchanged so downstream code paths
work without modification.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.agents._prompts import render, schema_example_block
from src.llm_clients.base import LLMClient
from src.schemas.evidence import EvidenceBundle
from src.schemas.issue import Issue
from src.schemas.paper import ParsedPaper
from src.schemas.summary import (
    Contribution,
    ExperimentsBlock,
    InitialSummary,
    MethodBlock,
)

# Hard cap on the final summary in words (Refine-OneVision constraint).
DEFAULT_MAX_WORDS = 1000


class RefinerOutput(BaseModel):
    """LLM-facing schema for the refiner. Excludes orchestrator-managed metadata."""

    tldr: str
    core_idea: str
    key_contributions: list[Contribution] = Field(default_factory=list)
    method: MethodBlock
    experiments: ExperimentsBlock
    limitations: list[str] = Field(default_factory=list)
    issues_addressed: list[str] = Field(
        default_factory=list,
        description="IDs of issues the refiner believes it has resolved.",
    )


class SingleDraftRefinerAgent:
    """Augment one winning draft with verifier-found missing/distorted facts."""

    def __init__(self, client: LLMClient, max_words: int = DEFAULT_MAX_WORDS):
        self.client = client
        self.max_words = max_words

    async def run(
        self,
        paper: ParsedPaper,
        winning_draft: InitialSummary,
        issues: list[Issue],
        evidence_bundles: list[EvidenceBundle],
    ) -> RefinerOutput:
        system = (
            render("refiner_onevision", "system", max_words=self.max_words)
            + "\n\n"
            + schema_example_block(RefinerOutput)
        )
        user = render(
            "refiner_onevision", "user",
            paper=paper,
            draft=winning_draft,
            issues=issues,
            evidence_bundles=evidence_bundles,
            max_words=self.max_words,
        )
        return await self.client.generate(
            system_prompt=system,
            user_prompt=user,
            response_schema=RefinerOutput,
            temperature=0.3,
            max_tokens=6144,
        )
