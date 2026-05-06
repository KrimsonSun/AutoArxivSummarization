"""Step 6 of strict-mode evaluation — paper-side recall.

For each PaperClaim (extracted from the source paper), ask the LLM:
    "Does the summary mention / cover this paper claim?"

Output: list[PaperClaimCoverage] with verdicts Covered / Partial / NotCovered.
This gives us recall = covered / total_paper_claims, complementing the
existing summary-side precision (evidence_coverage).

Implementation: single batched LLM call across all paper claims to keep
cost bounded (one call per (paper, summary) pair, not per claim).
"""
from __future__ import annotations

from src.llm_client import LLMClient, LLMError
from src.schemas import (
    CoverageVerdict,
    PaperClaim,
    PaperClaimCoverage,
    PaperCoverageList,
)


_SYSTEM = """You determine whether a summary covers each of the paper's atomic claims.

You will be given:
  • A list of paper claims (each with an ID PC1, PC2, ...).
  • The full text of a summary.

For each paper claim, decide:
  Covered     — The summary clearly mentions this fact (specific numbers, names,
                methods preserved).
  Partial     — The summary alludes to this aspect but lacks the specific
                quantitative or technical detail (e.g., paper claim says
                "achieves 28.4 BLEU on WMT 2014" but summary just says
                "achieves state-of-the-art").
  NotCovered  — The summary does NOT mention this fact at all.

Be strict on Covered: require the specific facts (numbers, names, dataset
identifiers) to appear in or near-paraphrase form in the summary. Vague
restatements should be Partial, not Covered.

Output JSON:
{"items": [{"claim_id": "PC1", "verdict": "Covered", "rationale": "..."}, ...]}"""


class RecallChecker:
    def __init__(self, client: LLMClient):
        self.client = client

    async def run(
        self,
        paper_claims: list[PaperClaim],
        summary_text: str,
    ) -> list[PaperClaimCoverage]:
        if not paper_claims:
            return []
        claims_block = "\n".join(
            f"[{c.id}] (from paragraph {c.source_paragraph_id or '?'}): {c.text}"
            for c in paper_claims
        )
        # Trim summary text if absurdly long (shouldn't happen — summaries are short).
        summary_text = summary_text[:30_000]
        user = (
            f"Paper claims to check:\n\n{claims_block}\n\n"
            f"Summary text:\n\n{summary_text}\n\n"
            f"For EACH of the {len(paper_claims)} paper claims above, output a "
            f"verdict (Covered / Partial / NotCovered). Output JSON shaped "
            f"{{\"items\": [...]}}."
        )
        try:
            result: PaperCoverageList = await self.client.generate(
                system_prompt=_SYSTEM,
                user_prompt=user,
                response_schema=PaperCoverageList,
                # 40 verdicts × ~150 tokens each (verdict + rationale) can hit
                # 6k. PaLM 2 (largest paper, 40 claims, longer rationales) hit
                # 8k. Bump to 16k for safety on the largest papers.
                max_tokens=16384,
            )
        except LLMError:
            # Conservative fallback: mark all as NotCovered (penalises us, not the summary).
            return [
                PaperClaimCoverage(
                    claim_id=c.id,
                    verdict=CoverageVerdict.NOT_COVERED,
                    rationale="Recall checker LLM call failed; defaulted to NotCovered.",
                )
                for c in paper_claims
            ]

        # Filter to known claim IDs (defensive against hallucination).
        valid_ids = {c.id for c in paper_claims}
        out: dict[str, PaperClaimCoverage] = {}
        for item in result.items:
            if item.claim_id not in valid_ids:
                continue
            if item.claim_id in out:
                continue
            out[item.claim_id] = item

        # Fill in any missing claim_ids (LLM dropped them) as NotCovered.
        full = []
        for c in paper_claims:
            if c.id in out:
                full.append(out[c.id])
            else:
                full.append(
                    PaperClaimCoverage(
                        claim_id=c.id,
                        verdict=CoverageVerdict.NOT_COVERED,
                        rationale="LLM did not return a verdict for this claim.",
                    )
                )
        return full
