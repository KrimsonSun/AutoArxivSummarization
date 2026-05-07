"""YAML config → typed PipelineConfig (handoff §6)."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    id: str | None = None
    provider: str  # "openai" | "anthropic" | "google"
    model: str
    temperature: float = 0.7


class VotingSpec(BaseModel):
    rounds: int = 3
    seed: int = 42


class RefinementSpec(BaseModel):
    """Stage 3-5 (verify / retrieve / refine) loop config.

    rounds=1 = single-pass refinement (the v1 default).
    rounds>1 = iterative: each round's output becomes the next round's
              draft input to the verifier.

    use_winner_as_refiner=True replaces the static `pipeline_llm` refiner
    with the LLM client of the agent that won Stage 2 voting. This avoids
    the v1 failure mode where a Llama-based refiner edited Qwen drafts
    and degraded their specifics.
    """
    rounds: int = 1
    use_winner_as_refiner: bool = False


class PipelineSection(BaseModel):
    initial_agents: list[AgentSpec]
    pipeline_llm: AgentSpec
    voting: VotingSpec = Field(default_factory=VotingSpec)
    refinement: RefinementSpec = Field(default_factory=RefinementSpec)
    max_summary_words: int = Field(
        default=1000,
        description="Hard word cap applied to drafts AND the final summary.",
    )


class ConstraintsSection(BaseModel):
    max_issues: int = 12
    max_evidence_per_issue: int = 3
    max_paragraphs_in_refiner_context: int = 50
    llm_timeout_seconds: int = 120
    max_retries: int = 2


class OutputSection(BaseModel):
    json_output_dir: str = "outputs/json"
    markdown_output_dir: str = "outputs/markdown"
    emit_markdown: bool = True


class LoggingSection(BaseModel):
    level: str = "INFO"
    json_logs: bool = True


class PipelineConfig(BaseModel):
    pipeline: PipelineSection
    constraints: ConstraintsSection = Field(default_factory=ConstraintsSection)
    output: OutputSection = Field(default_factory=OutputSection)
    logging: LoggingSection = Field(default_factory=LoggingSection)


def load_config(path: str | Path) -> PipelineConfig:
    p = Path(path)
    if not p.is_absolute():
        # Resolve relative to project root.
        project_root = Path(__file__).resolve().parents[2]
        p = project_root / p
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PipelineConfig.model_validate(data)
