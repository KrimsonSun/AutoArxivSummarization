"""FinalSummary → human-readable Markdown (handoff §2.6).

No LLM calls — pure string formatting. Used as a fallback display format
for the website and for log inspection during development.
"""
from __future__ import annotations

from src.schemas.summary import FinalSummary


def to_markdown(summary: FinalSummary) -> str:
    md: list[str] = []
    md.append(f"# {summary.metadata.title}")
    md.append("")
    if summary.metadata.arxiv_id:
        md.append(f"*arXiv ID:* `{summary.metadata.arxiv_id}`  ")
    md.append(
        f"*Generated:* {summary.metadata.timestamp}  "
        f"*Pipeline LLM:* `{summary.metadata.pipeline_llm}`  "
        f"*Initial agents:* {', '.join(summary.metadata.initial_agents)}"
    )
    md.append("")

    md.append("## TL;DR")
    md.append(summary.tldr)
    md.append("")

    md.append("## Core Idea")
    md.append(summary.core_idea)
    md.append("")

    md.append("## Key Contributions")
    if not summary.key_contributions:
        md.append("_None reported._")
    for i, c in enumerate(summary.key_contributions, start=1):
        refs = _refs(c.evidence_refs)
        md.append(f"{i}. {c.text}{refs}")
    md.append("")

    md.append("## Method")
    md.append(f"**Overview.** {summary.method.overview}")
    md.append("")
    if summary.method.components:
        md.append("**Components.**")
        for comp in summary.method.components:
            refs = _refs(comp.evidence_refs)
            md.append(f"- **{comp.name}.** {comp.description}{refs}")
        md.append("")

    md.append("## Experiments")
    md.append(f"**Setup.** {summary.experiments.setup}")
    md.append("")
    if summary.experiments.key_findings:
        md.append("**Key findings.**")
        for f in summary.experiments.key_findings:
            refs = _refs(f.evidence_refs)
            md.append(f"- {f.text}{refs}")
        md.append("")

    md.append("## Limitations")
    if not summary.limitations:
        md.append("_None reported._")
    else:
        for lim in summary.limitations:
            md.append(f"- {lim}")
    md.append("")

    md.append("---")
    md.append("## Pipeline Metadata")
    m = summary.metadata
    md.append(f"- Paper paragraphs: {m.paper_paragraph_count}")
    md.append(f"- Issues raised by verifier: {m.issues_raised}")
    md.append(f"- Issues addressed by refiner: {len(m.issues_addressed)}")
    md.append(
        f"- Evidence paragraphs used: "
        f"{', '.join(m.evidence_paragraphs_used) if m.evidence_paragraphs_used else 'none'}"
    )
    md.append(
        f"- LLM calls: {m.total_llm_calls} "
        f"(prompt={m.total_tokens_used.get('prompt', 0)}, "
        f"completion={m.total_tokens_used.get('completion', 0)} tokens)"
    )
    if m.failed_initial_agents:
        md.append(f"- Failed initial agents: {', '.join(m.failed_initial_agents)}")
    if m.truncated:
        md.append("- ⚠️ Paper was truncated to fit refiner context.")

    return "\n".join(md)


def _refs(refs: list[str]) -> str:
    if not refs:
        return ""
    return f" _[{', '.join(refs)}]_"
