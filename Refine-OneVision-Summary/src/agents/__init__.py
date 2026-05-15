"""Refine-OneVision agents.

Note: the v1 ``RefinerAgent`` / ``VerifierAgent`` / ``PeerReviewVerifier``
have been replaced by the OneVision variants below. The ``EvidenceRetriever``
and ``InitialSummarizer`` are reused (with updated prompts that enforce the
1000-word cap on drafts).
"""
from src.agents.claim_grounding_voter import ClaimGroundingVoter
from src.agents.refiner import (
    DEFAULT_MAX_WORDS,
    RefinerOutput,
    SingleDraftRefinerAgent,
)
from src.agents.retriever import EvidenceRetrieverAgent
from src.agents.summarizer import InitialSummarizerAgent
from src.agents.verifier import MAX_ISSUES, SingleDraftVerifierAgent
from src.agents.voter import GameTheoryVoter, VoterClient

__all__ = [
    "ClaimGroundingVoter",
    "DEFAULT_MAX_WORDS",
    "EvidenceRetrieverAgent",
    "GameTheoryVoter",
    "InitialSummarizerAgent",
    "MAX_ISSUES",
    "RefinerOutput",
    "SingleDraftRefinerAgent",
    "SingleDraftVerifierAgent",
    "VoterClient",
]
