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
