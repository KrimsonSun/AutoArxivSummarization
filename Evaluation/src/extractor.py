"""Step 1 — Claim extraction.

Decomposes a summary into atomic factual claims. Accepts a flexible input:
either a structured FinalSummary JSON (from RefinedSummarization), or any
plain string (for baseline summaries). When given a FinalSummary, claim
``source_field`` traces back to the originating field for paper appendix.
"""
from __future__ import annotations

from typing import Any

from src.llm_client import LLMClient
from src.schemas import Claim, ClaimList


# --- prompt -------------------------------------------------------------------

_SYSTEM = """You decompose academic-paper summaries into atomic factual claims.

A "claim" is a single, self-contained, verifiable factual statement. Examples:
  Good:  "The Transformer achieves 28.4 BLEU on WMT 2014 English-to-German."
  Bad:   "The Transformer is good." (not verifiable / not specific)
  Bad:   "The Transformer is a model that uses attention and is fast." (compound)

Rules:
1. Each claim must be ONE assertion. Split compound sentences.
2. Use the most specific, quantitative form available in the source text.
3. Do NOT introduce facts not in the source — paraphrase only.
4. Skip purely meta sentences ("This paper discusses...") and section headers.
5. Output JSON: {"claims": [{"id": "C1", "text": "...", "source_field": "..."}, ...]}
   `source_field` is the section name passed in the user message (e.g. "tldr",
   "key_contributions", "method.overview"). Echo it verbatim.
6. IDs must be sequential C1, C2, ... across the entire summary."""


class ClaimExtractor:
    """One LLM call per logical section. Concurrency handled by the orchestrator."""

    def __init__(self, client: LLMClient):
        self.client = client

    async def from_final_summary(self, final_summary: dict) -> list[Claim]:
        """FinalSummary JSON → atomic claims (with source_field traceability)."""
        section_texts = _flatten_final_summary(final_summary)
        return await self._extract_sections(section_texts)

    async def from_plain_text(self, text: str) -> list[Claim]:
        """Plain text → atomic claims (used for baseline summaries)."""
        return await self._extract_sections([("summary", text)])

    # ------------------------------------------------------------ internal

    async def _extract_sections(
        self, sections: list[tuple[str, str]]
    ) -> list[Claim]:
        # One batched call across all sections — keeps IDs globally unique.
        if not any(text.strip() for _, text in sections):
            return []
        body_lines: list[str] = []
        for section_name, text in sections:
            text = text.strip()
            if not text:
                continue
            body_lines.append(f"[source_field: {section_name}]")
            body_lines.append(text)
            body_lines.append("")
        user = (
            "Decompose the following summary text into atomic factual claims.\n"
            "Each claim must record its `source_field` from the bracketed tag.\n\n"
            + "\n".join(body_lines)
        )
        result: ClaimList = await self.client.generate(
            system_prompt=_SYSTEM,
            user_prompt=user,
            response_schema=ClaimList,
        )
        # Normalise IDs in case the model re-numbered or skipped.
        return [
            Claim(id=f"C{i + 1}", text=c.text, source_field=c.source_field)
            for i, c in enumerate(result.claims)
        ]


# ------------------------------------------------------- helper: flatten summary

def _flatten_final_summary(fs: dict) -> list[tuple[str, str]]:
    """Walk the FinalSummary JSON and yield (source_field, text) pairs.

    Tolerant to missing keys so it also works on partial / baseline summaries
    that share some of the same shape.
    """
    out: list[tuple[str, str]] = []

    def _add(field: str, value: Any) -> None:
        if isinstance(value, str) and value.strip():
            out.append((field, value))

    _add("tldr", fs.get("tldr"))
    _add("core_idea", fs.get("core_idea"))

    for i, c in enumerate(fs.get("key_contributions") or []):
        if isinstance(c, dict):
            _add(f"key_contributions[{i}]", c.get("text"))
        elif isinstance(c, str):
            _add(f"key_contributions[{i}]", c)

    method = fs.get("method") or {}
    if isinstance(method, dict):
        _add("method.overview", method.get("overview"))
        for i, comp in enumerate(method.get("components") or []):
            if isinstance(comp, dict):
                name = comp.get("name", f"component_{i}")
                _add(f"method.components[{name}]", comp.get("description"))

    experiments = fs.get("experiments") or {}
    if isinstance(experiments, dict):
        _add("experiments.setup", experiments.get("setup"))
        for i, f in enumerate(experiments.get("key_findings") or []):
            if isinstance(f, dict):
                _add(f"experiments.key_findings[{i}]", f.get("text"))

    for i, lim in enumerate(fs.get("limitations") or []):
        if isinstance(lim, str):
            _add(f"limitations[{i}]", lim)

    return out
