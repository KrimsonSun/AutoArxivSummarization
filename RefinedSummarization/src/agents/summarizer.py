"""Initial Summarizer agent (handoff §2.2, §4.2)."""
from __future__ import annotations

from src.agents._prompts import render, schema_example_block
from src.llm_clients.base import LLMClient
from src.schemas.paper import ParsedPaper
from src.schemas.summary import InitialSummary


class InitialSummarizerAgent:
    """Stateless: one PDF → one InitialSummary using a specific LLMClient."""

    def __init__(self, client: LLMClient, agent_id: str):
        self.client = client
        self.agent_id = agent_id

    async def run(self, paper: ParsedPaper) -> InitialSummary:
        system = (
            render("initial_summarizer", "system", agent_id=self.agent_id)
            + "\n\n"
            + schema_example_block(InitialSummary)
        )
        user = render("initial_summarizer", "user", paper=paper)
        result = await self.client.generate(
            system_prompt=system,
            user_prompt=user,
            response_schema=InitialSummary,
            temperature=0.7,
            max_tokens=4096,
        )
        # Force agent_id to be the configured one (model sometimes ignores).
        result.agent_id = self.agent_id
        return result
