"""Paper-side atomic claim extraction (Step 5 of strict-mode evaluation).

Runs ONCE per paper (not per summary), so we cache the result on disk and
re-use it across all 6 summaries (Ours + 5 baselines) for that paper.

Strategy:
  - Concatenate paper paragraphs in order.
  - Single batched LLM call extracts atomic factual claims, each tagged with
    its source paragraph ID for traceability.
  - Cap the number of paper claims at MAX_PAPER_CLAIMS to keep the recall
    LLM call within context budget.

Why limit claims? With 50+ paper claims × per-claim verification, costs
scale linearly. We sample the most important ones (LLM picks them) up to
the cap. For typical 10-page papers, ~30 atomic claims is the right range.
"""
from __future__ import annotations

from src.llm_client import LLMClient
from src.schemas import PaperBundle, PaperClaim, PaperClaimList

MAX_PAPER_CLAIMS = 40


_SYSTEM = """You decompose an academic paper into atomic factual claims.

A "claim" is a SINGLE, VERIFIABLE, SPECIFIC factual statement from the paper.
We will later check whether a summary covers each of these. Pick the most
IMPORTANT claims a competent summary should mention — not every minor detail.

What to extract:
  • Quantitative results (numbers, BLEU/F1/accuracy, dataset sizes)
  • Specific method components / architectural choices
  • Concrete contributions ("we propose X to solve Y")
  • Stated limitations
  • Key experimental setup facts (datasets, baselines compared)

What NOT to extract:
  • Generic motivation ("RNNs have limitations")
  • Trivial restatements of common knowledge
  • Citations / related-work descriptions

Rules:
1. Output AT MOST {max} claims, sorted by importance.
2. Each claim is ONE assertion (no compound statements).
3. Use the paper's exact terminology and exact numbers.
4. Tag each claim with its source paragraph ID (e.g., "P5") if you can.
5. Output JSON: {{"claims": [{{"id": "PC1", "text": "...", "source_paragraph_id": "P5"}}, ...]}}
6. IDs must be sequential PC1, PC2, ..."""


class PaperClaimExtractor:
    def __init__(self, client: LLMClient, max_claims: int = MAX_PAPER_CLAIMS):
        self.client = client
        self.max_claims = max_claims

    async def run(self, paper: PaperBundle) -> list[PaperClaim]:
        if not paper.paragraphs:
            return []
        # Build the user message — paragraphs with IDs.
        # Trim to fit context (Llama-70B has 128k but stay safe ~50k chars).
        body_lines: list[str] = []
        budget = 50_000
        used = 0
        for p in paper.paragraphs:
            line = f"[{p.id}] {p.text}"
            if used + len(line) > budget:
                break
            body_lines.append(line)
            used += len(line) + 2

        user = (
            f"Paper title: {paper.title}\n\n"
            "Paper paragraphs:\n\n"
            + "\n\n".join(body_lines)
            + f"\n\nExtract up to {self.max_claims} atomic factual claims now. "
            f"Output JSON {{\"claims\": [...]}}."
        )

        result: PaperClaimList = await self.client.generate(
            system_prompt=_SYSTEM.format(max=self.max_claims),
            user_prompt=user,
            response_schema=PaperClaimList,
            max_tokens=4096,
        )
        # Normalise IDs and trim to cap.
        return [
            PaperClaim(
                id=f"PC{i + 1}",
                text=c.text,
                source_paragraph_id=c.source_paragraph_id,
            )
            for i, c in enumerate(result.claims[: self.max_claims])
        ]
