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


class ParagraphSummarizerSpec(BaseModel):
    provider: str
    model: str
    temperature: float = 0.0
    target_length: int = 200


class PipelineSection(BaseModel):
    initial_agents: list[AgentSpec]
    pipeline_llm: AgentSpec
    paragraph_summarizer: ParagraphSummarizerSpec | None = None
    verification_mode: str = Field(
        default="mutual_peer_review",
        description=(
            "How issues are surfaced. Options:\n"
            " - 'mutual_peer_review' (default): the same 3 heterogeneous LLMs "
            "   that wrote the drafts each independently critique all 3 drafts. "
            "   Issues are aggregated across reviewers, with raised_by tags "
            "   indicating consensus. This is the canonical multi-agent debate "
            "   variant for mutual evaluation.\n"
            " - 'single_judge': a single pipeline_llm acts as the sole verifier "
            "   (HANDOFF §1.2 default; kept for ablation experiments)."
        ),
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
