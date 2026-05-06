"""DeBERTa-v3-NLI verifier — alternative to LLM-as-judge.

Why this exists:
  Step 3 of the evaluation pipeline (verify whether evidence supports a claim)
  is currently done by an LLM (Llama 3.3 70B). Same model also does claim
  extraction in Step 1. That self-favoring bias inflates Supported verdicts
  on vague claims (see analysis: methods all score 0.95+ in loose mode).

  DeBERTa-v3-base-mnli-fever-anli is a 86M-param classifier fine-tuned on
  ~800k human-labelled NLI examples (MNLI + FEVER + ANLI). It outputs
  calibrated softmax probabilities for {entailment, neutral, contradiction}
  given a (premise, hypothesis) pair.

  Key advantages over LLM-as-judge:
    - Fully decoupled from the claim-extraction LLM (no self-bias)
    - Calibrated probabilities, not free-form text
    - Deterministic given fixed weights (no temperature non-determinism)
    - 50 ms / pair on CPU, ~2 ms / pair on MPS / CUDA
    - Free at inference (one-time ~250 MB weight download)

How we map 3-class NLI → our 4-class verdict:
  Per claim, run NLI against EACH retrieved paragraph separately.
  Take the MAX entailment and MAX contradiction across all paragraphs.

  - max_contradiction > contradiction_threshold (default 0.50) → Contradicted
  - max_entailment    > entailment_threshold     (default 0.70) → Supported
  - max_entailment    > partial_threshold        (default 0.30) → Partial
  - else                                                        → Unsupported

Thresholds are tunable in config (scoring.nli_*). The defaults are
literature-typical (SummaC, FacTool) but should be calibrated against a
small gold-labeled set for a real paper submission.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.schemas import Claim, ClaimVerification, EvidenceChunk, Verdict


# Default model. DeBERTa-v3-large-mnli-fever-anli is stronger but 4x larger;
# base is the sweet spot for accuracy / speed. Both Hugging Face hub IDs.
DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


@dataclass
class NLIThresholds:
    entailment_supported: float = 0.70
    entailment_partial: float = 0.30
    contradiction_strong: float = 0.50


class NLIVerifier:
    """Drop-in replacement for ``ClaimVerifier`` using a local NLI classifier."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        thresholds: NLIThresholds | None = None,
        device: str | None = None,
    ):
        # Lazy-import so importing this module doesn't pull torch unless used.
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device
        self.thresholds = thresholds or NLIThresholds()

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(device)
        self.model.eval()

        # Map output indices to label names. DeBERTa-v3-mnli uses
        # id2label = {0: "entailment", 1: "neutral", 2: "contradiction"}
        # but we look it up dynamically to be safe across model versions.
        self._id2label = {
            int(k): v.lower() for k, v in self.model.config.id2label.items()
        }

    async def run(
        self,
        claim: Claim,
        evidence: list[EvidenceChunk],
    ) -> ClaimVerification:
        """Async-compatible signature matching ClaimVerifier — but runs sync
        torch inference under the hood (negligible blocking time per call).
        """
        if not evidence:
            return ClaimVerification(
                claim_id=claim.id,
                verdict=Verdict.UNSUPPORTED,
                rationale="No evidence retrieved.",
                evidence_paragraphs=[],
            )

        max_entail = 0.0
        max_contra = 0.0
        best_entail_pid: str | None = None
        best_contra_pid: str | None = None
        per_para_scores: list[tuple[str, float, float]] = []

        for ev in evidence:
            entail, neutral, contra = self._infer(ev.text, claim.text)
            per_para_scores.append((ev.paragraph_id, entail, contra))
            if entail > max_entail:
                max_entail = entail
                best_entail_pid = ev.paragraph_id
            if contra > max_contra:
                max_contra = contra
                best_contra_pid = ev.paragraph_id

        # Verdict mapping (priority: contradiction wins ties).
        if max_contra > self.thresholds.contradiction_strong and max_contra >= max_entail:
            verdict = Verdict.CONTRADICTED
            evidence_paragraphs = [best_contra_pid] if best_contra_pid else []
            rationale = (
                f"Strongest paragraph contradicts the claim "
                f"(P(contradiction)={max_contra:.2f}, P(entailment)={max_entail:.2f})."
            )
        elif max_entail > self.thresholds.entailment_supported:
            verdict = Verdict.SUPPORTED
            evidence_paragraphs = [best_entail_pid] if best_entail_pid else []
            rationale = (
                f"Paragraph entails the claim (P(entailment)={max_entail:.2f})."
            )
        elif max_entail > self.thresholds.entailment_partial:
            verdict = Verdict.PARTIAL
            evidence_paragraphs = [best_entail_pid] if best_entail_pid else []
            rationale = (
                f"Partial support only (P(entailment)={max_entail:.2f}, "
                f"below {self.thresholds.entailment_supported:.2f} for full support)."
            )
        else:
            verdict = Verdict.UNSUPPORTED
            evidence_paragraphs = []
            rationale = (
                f"No paragraph entails the claim "
                f"(max P(entailment)={max_entail:.2f})."
            )

        return ClaimVerification(
            claim_id=claim.id,
            verdict=verdict,
            rationale=rationale,
            evidence_paragraphs=evidence_paragraphs,
        )

    # ------------------------------------------------------------ internal

    def _infer(self, premise: str, hypothesis: str) -> tuple[float, float, float]:
        """Forward pass, return (P_entail, P_neutral, P_contra)."""
        import torch  # local import to avoid forcing torch import at module load

        # DeBERTa-v3 max length is 512. Truncate premise (paper paragraph)
        # if too long; keep hypothesis (claim) whole.
        inputs = self.tokenizer(
            premise,
            hypothesis,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            logits = self.model(**inputs).logits[0]  # shape: [3]
        probs = logits.softmax(dim=-1).cpu().tolist()

        # Map by label name in case the order differs across model versions.
        result = {
            self._id2label.get(i, str(i)): probs[i] for i in range(len(probs))
        }
        return (
            result.get("entailment", 0.0),
            result.get("neutral", 0.0),
            result.get("contradiction", 0.0),
        )
