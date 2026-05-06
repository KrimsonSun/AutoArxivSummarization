"""Step 3 — NLI-style verification.

For each (claim, retrieved_evidence) pair, ask the LLM:
    "Does the evidence support, partially support, fail to address, or
     contradict the claim?"

The LLM returns a typed ClaimVerification {verdict, rationale, evidence_refs}.
Failures are wrapped in LLMError but the orchestrator degrades gracefully —
a failed verification is recorded as ``Unsupported`` (conservative — counts
toward hallucination) so a flaky LLM call doesn't artificially inflate
coverage.
"""
from __future__ import annotations

from src.llm_client import LLMClient, LLMError
from src.schemas import Claim, ClaimVerification, EvidenceChunk, Verdict


_SYSTEM_LOOSE = """You verify whether evidence from an academic paper supports a specific claim.

You will be shown:
  • A claim (one atomic factual statement).
  • A small set of paper paragraphs that may be relevant evidence.

Decide which verdict applies:

  Supported     — The evidence directly entails the claim (the claim's facts
                  appear in the evidence and match).
  Partial       — The evidence supports PART of the claim but not all of it,
                  OR is consistent with the claim but doesn't fully verify it.
  Unsupported   — None of the evidence addresses the claim. (You cannot find
                  the claim's facts in the evidence at all.)
  Contradicted  — The evidence directly contradicts the claim.

Rules:
1. Be strict. "Plausibly true" is NOT support — only explicit evidence is.
2. If the claim mentions a specific number, the evidence must contain that
   number (or a close paraphrase) to be Supported.
3. Cite the paragraph IDs that drove your verdict in `evidence_paragraphs`.
4. If you mark Supported / Partial / Contradicted, `evidence_paragraphs` MUST
   be non-empty. If Unsupported, leave it empty.
5. Output JSON: {"claim_id": "...", "verdict": "...", "rationale": "...",
   "evidence_paragraphs": ["P3", "P5"]}"""


_SYSTEM_STRICT = """You verify whether evidence from an academic paper SPECIFICALLY supports a claim.

This is a STRICT verification regime: vague restatements of the paper's
themes do NOT count as Supported. Only specific, verifiable matches do.

Verdicts:

  Supported     — The evidence contains the claim's SPECIFIC facts:
                  • If the claim mentions a number/score (e.g. "28.4 BLEU"),
                    the evidence must contain that exact number (or near-paraphrase).
                  • If the claim names a method/dataset/architecture, the
                    evidence must mention it by name.
                  • Generic claims like "the paper proposes a new method" or
                    "achieves state-of-the-art" do NOT qualify as Supported
                    unless the evidence has the specific corresponding facts.
  Partial       — The claim has some support but is too vague OR the evidence
                  only partially matches the specifics. Most generic
                  claims land here.
  Unsupported   — The evidence does not address the claim at all.
  Contradicted  — The evidence directly contradicts the claim.

Rules:
1. Bias toward Partial when the claim is vague — generic restatements should
   NOT score as Supported.
2. Numbers / names / dataset identifiers MUST match. "Achieves 28.4 BLEU"
   ≠ "Achieves high BLEU". The latter is Partial at best.
3. Cite paragraph IDs that drove your verdict in `evidence_paragraphs`.
4. If Supported / Partial / Contradicted, `evidence_paragraphs` MUST be non-empty.
5. Output JSON: {"claim_id": "...", "verdict": "...", "rationale": "...",
   "evidence_paragraphs": ["P3", "P5"]}"""


class ClaimVerifier:
    def __init__(self, client: LLMClient, strict: bool = False):
        self.client = client
        self.strict = strict
        self._system = _SYSTEM_STRICT if strict else _SYSTEM_LOOSE

    async def run(
        self,
        claim: Claim,
        evidence: list[EvidenceChunk],
    ) -> ClaimVerification:
        if not evidence:
            # No retrieval hit — by definition there's nothing to support
            # the claim. Mark Unsupported without burning an LLM call.
            return ClaimVerification(
                claim_id=claim.id,
                verdict=Verdict.UNSUPPORTED,
                rationale="No paper paragraphs were retrieved as evidence.",
                evidence_paragraphs=[],
            )
        user = _render_user(claim, evidence)
        try:
            verdict = await self.client.generate(
                system_prompt=self._system,
                user_prompt=user,
                response_schema=ClaimVerification,
            )
        except LLMError:
            # Conservative degradation: count as Unsupported (penalises us,
            # not the summary, when the verifier itself misbehaves).
            return ClaimVerification(
                claim_id=claim.id,
                verdict=Verdict.UNSUPPORTED,
                rationale="Verifier LLM call failed; defaulted to Unsupported.",
                evidence_paragraphs=[],
            )
        # Force the model's claim_id to match (some models echo the wrong one).
        verdict.claim_id = claim.id
        # Filter evidence_paragraphs to retrieved IDs (anti-hallucination).
        retrieved_ids = {ev.paragraph_id for ev in evidence}
        verdict.evidence_paragraphs = [
            pid for pid in verdict.evidence_paragraphs if pid in retrieved_ids
        ]
        return verdict


def _render_user(claim: Claim, evidence: list[EvidenceChunk]) -> str:
    chunks = "\n\n".join(
        f"[{ev.paragraph_id} | retrieval_score={ev.score:.3f}]\n{ev.text}"
        for ev in evidence
    )
    return (
        f"Claim ID: {claim.id}\n"
        f"Claim: {claim.text}\n"
        f"(Source field in summary: {claim.source_field or 'unknown'})\n\n"
        f"Retrieved evidence paragraphs (top-{len(evidence)} from BM25 / embedding):\n\n"
        f"{chunks}\n\n"
        f"Output the ClaimVerification JSON now."
    )
