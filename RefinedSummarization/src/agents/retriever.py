"""Evidence Retriever agent (handoff §2.4, §4.2).

Anti-hallucination guarantee: the LLM only ever returns paragraph IDs and a
relevance explanation. Paragraph TEXT is filled in by Python from the
ParsedPaper, so the LLM cannot fabricate or rewrite source content.
"""
from __future__ import annotations

from src.agents._prompts import render, schema_example_block
from src.llm_clients.base import LLMClient
from src.schemas.evidence import EvidenceBundle, EvidenceItem, EvidenceSelectionList
from src.schemas.issue import Issue
from src.schemas.paper import ParsedPaper

MAX_EVIDENCE_PER_ISSUE = 3


class EvidenceRetrieverAgent:
    def __init__(self, client: LLMClient):
        self.client = client

    async def run(self, issue: Issue, paper: ParsedPaper) -> EvidenceBundle:
        system = render("retriever", "system") + "\n\n" + schema_example_block(EvidenceSelectionList)
        user = render("retriever", "user", issue=issue, paper=paper)
        try:
            selection: EvidenceSelectionList = await self.client.generate(
                system_prompt=system,
                user_prompt=user,
                response_schema=EvidenceSelectionList,
                temperature=0.3,
                max_tokens=1024,
            )
        except Exception:
            # Retriever failures degrade gracefully — refiner can still merge
            # using the verifier's verdict alone.
            return EvidenceBundle(issue_id=issue.id, evidence=[])

        # Materialise each selection into an EvidenceItem with REAL text from
        # the parsed paper. Skip IDs that don't exist (LLM hallucination guard).
        items: list[EvidenceItem] = []
        seen_ids: set[str] = set()
        for sel in selection.selections[:MAX_EVIDENCE_PER_ISSUE]:
            if sel.paragraph_id in seen_ids:
                continue
            paragraph = paper.paragraph_by_id(sel.paragraph_id)
            if paragraph is None:
                continue
            seen_ids.add(sel.paragraph_id)
            items.append(
                EvidenceItem(
                    paragraph_id=paragraph.id,
                    text=paragraph.text,
                    relevance_explanation=sel.relevance_explanation,
                )
            )
        return EvidenceBundle(issue_id=issue.id, evidence=items)
