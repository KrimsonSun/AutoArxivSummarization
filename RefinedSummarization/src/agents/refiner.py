"""Refiner agent (handoff §2.5, §4.2).

The refiner produces the FinalSummary content and self-reports which issues
it actually addressed (the orchestrator wraps everything else into metadata).

We use a slimmer schema (RefinerOutput) for the LLM call because metadata
fields are populated outside this agent.
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


class RefinerAgent:
    def __init__(self, client: LLMClient):
        self.client = client

    async def run(
        self,
        paper: ParsedPaper,
        summaries: list[InitialSummary],
        issues: list[Issue],
        evidence_bundles: list[EvidenceBundle],
    ) -> RefinerOutput:
        system = render("refiner", "system") + "\n\n" + schema_example_block(RefinerOutput)
        user = render(
            "refiner",
            "user",
            paper=paper,
            summaries=summaries,
            issues=issues,
            evidence_bundles=evidence_bundles,
        )
        # Use a generous max_tokens because the refiner emits the full summary.
        return await self.client.generate(
            system_prompt=system,
            user_prompt=user,
            response_schema=RefinerOutput,
            temperature=0.3,
            max_tokens=6144,
        )
