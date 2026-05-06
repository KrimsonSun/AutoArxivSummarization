"""YAML config → typed EvalConfig."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ModelSpec(BaseModel):
    provider: str = "openai"
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024


class RetrievalSpec(BaseModel):
    method: str = "bm25"  # bm25 | embedding
    top_k: int = 5


class ScoringSpec(BaseModel):
    partial_credit: float = 0.5
    unsupported_is_hallucination: bool = True
    strict_mode: bool = Field(
        default=False,
        description=(
            "If True, also extract atomic claims from the PAPER and compute "
            "paper_recall + F1. This is the FActScore-style recall check that "
            "guards against summaries gaming precision by writing few claims."
        ),
    )
    strict_verifier_prompt: bool = Field(
        default=False,
        description=(
            "If True (and verifier_kind=llm), the verifier requires explicit "
            "quantitative match for Supported. Ignored when verifier_kind=deberta_nli."
        ),
    )
    verifier_kind: str = Field(
        default="llm",
        description=(
            "Which verifier to use for Step 3:\n"
            "  llm          — LLM-as-judge (Llama 3.3 70B by default).\n"
            "  deberta_nli  — Local DeBERTa-v3-NLI classifier. Decoupled from\n"
            "                 the claim-extraction LLM, calibrated probabilities,\n"
            "                 ~250 MB one-time download. ~50 ms / pair on CPU."
        ),
    )
    nli_model: str = Field(
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        description="Hugging Face model id for verifier_kind=deberta_nli.",
    )
    nli_entailment_supported: float = 0.70
    nli_entailment_partial: float = 0.30
    nli_contradiction_strong: float = 0.50


class LoggingSpec(BaseModel):
    level: str = "INFO"
    json_logs: bool = False


class EvalConfig(BaseModel):
    extractor: ModelSpec
    verifier: ModelSpec
    retrieval: RetrievalSpec = Field(default_factory=RetrievalSpec)
    scoring: ScoringSpec = Field(default_factory=ScoringSpec)
    logging: LoggingSpec = Field(default_factory=LoggingSpec)


def load_config(path: str | Path) -> EvalConfig:
    p = Path(path)
    if not p.is_absolute():
        project_root = Path(__file__).resolve().parents[1]
        p = project_root / p
    with open(p, "r", encoding="utf-8") as f:
        return EvalConfig.model_validate(yaml.safe_load(f))
