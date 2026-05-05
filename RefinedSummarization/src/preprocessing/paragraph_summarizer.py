"""Pre-compute a ~200-char summary of every paragraph (handoff §2.4 last note).

The retriever prompt would otherwise have to send the full paragraph text for
every paragraph in the paper, blowing up token usage. Pre-summarising once
with a cheap model (e.g. ``gpt-4o-mini``) keeps the retriever fast and lets
the verifier display compact context.

Implementation: a single batched LLM call per paper. We send all paragraphs in
one prompt and ask for an array of {id, summary_short} back. With 50–200
paragraphs at <500 chars each, this fits in a single ~30k input + ~10k output
call to a small model.

Falls back to a deterministic head-of-text shortener if no LLM client is
available (DEV_MODE) — the pipeline still works, just with slightly wordier
retriever prompts.
"""
from __future__ import annotations

import asyncio
import textwrap

from pydantic import BaseModel, Field

from src.llm_clients.base import LLMClient
from src.schemas.paper import ParsedPaper


class _ShortSummary(BaseModel):
    id: str
    summary_short: str


class _ShortSummaryList(BaseModel):
    items: list[_ShortSummary] = Field(default_factory=list)


class ParagraphShortSummarizer:
    """Fills in ``paragraph.summary_short`` for every paragraph in-place."""

    def __init__(self, client: LLMClient | None, target_length: int = 200):
        self.client = client
        self.target_length = target_length

    async def run(self, paper: ParsedPaper) -> ParsedPaper:
        if self.client is None:
            for p in paper.paragraphs:
                p.summary_short = self._fallback(p.text)
            return paper

        # Batch into one (or a few) calls. Keep input <60k chars.
        chunks: list[list[int]] = self._chunk_paragraphs(paper, max_chars=50_000)
        for chunk_indices in chunks:
            chunk_text = "\n".join(
                f"[{paper.paragraphs[i].id}] {paper.paragraphs[i].text}"
                for i in chunk_indices
            )
            system = (
                "You compress academic-paper paragraphs into short summaries. "
                f"For each input paragraph, return a one-sentence summary of "
                f"~{self.target_length} characters that preserves the technical "
                "claim or fact. Do not add information that isn't in the original."
            )
            user = (
                "Return JSON {\"items\": [{\"id\": \"P1\", \"summary_short\": \"...\"}, ...]} "
                "with one item per input paragraph, in the same order.\n\n"
                f"{chunk_text}"
            )
            try:
                result: _ShortSummaryList = await self.client.generate(
                    system_prompt=system,
                    user_prompt=user,
                    response_schema=_ShortSummaryList,
                    temperature=0.0,
                    max_tokens=4096,
                )
            except Exception:
                # Robust fallback: do not let summarisation failure crash the pipeline.
                for i in chunk_indices:
                    paper.paragraphs[i].summary_short = self._fallback(
                        paper.paragraphs[i].text
                    )
                continue

            by_id = {item.id: item.summary_short for item in result.items}
            for i in chunk_indices:
                p = paper.paragraphs[i]
                p.summary_short = by_id.get(p.id) or self._fallback(p.text)
        return paper

    def _chunk_paragraphs(self, paper: ParsedPaper, max_chars: int) -> list[list[int]]:
        chunks: list[list[int]] = []
        current: list[int] = []
        current_len = 0
        for i, p in enumerate(paper.paragraphs):
            length = len(p.text) + len(p.id) + 4
            if current and current_len + length > max_chars:
                chunks.append(current)
                current, current_len = [], 0
            current.append(i)
            current_len += length
        if current:
            chunks.append(current)
        return chunks

    def _fallback(self, text: str) -> str:
        # First-N-chars fallback (handoff allows this when LLM is unavailable).
        if len(text) <= self.target_length:
            return text
        cut = textwrap.shorten(text, width=self.target_length, placeholder="…")
        return cut


__all__ = ["ParagraphShortSummarizer"]
