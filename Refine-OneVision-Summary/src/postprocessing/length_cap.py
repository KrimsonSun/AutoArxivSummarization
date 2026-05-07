"""Hard 1000-word cap for the OneVision pipeline.

Even with explicit prompt-side instructions, LLMs sometimes overshoot.
This module provides a deterministic post-hoc truncation utility that
operates on (a) the structured summary fields proportionally, and
(b) the markdown rendering as a safety net.
"""
from __future__ import annotations

import re
from typing import TypeVar

from src.schemas.summary import (
    Contribution,
    ExperimentFinding,
    ExperimentsBlock,
    InitialSummary,
    MethodBlock,
    MethodComponent,
)

T = TypeVar("T")


def _word_count(s: str) -> int:
    """Count words by simple whitespace splitting."""
    return len(s.split()) if s else 0


def total_words(summary: InitialSummary) -> int:
    """Total word count across all human-readable text fields."""
    n = 0
    n += _word_count(summary.tldr)
    n += _word_count(summary.core_idea)
    for c in summary.key_contributions:
        n += _word_count(c.text)
    n += _word_count(summary.method.overview)
    for comp in summary.method.components:
        n += _word_count(comp.name) + _word_count(comp.description)
    n += _word_count(summary.experiments.setup)
    for f in summary.experiments.key_findings:
        n += _word_count(f.text)
    for lim in summary.limitations:
        n += _word_count(lim)
    return n


def _truncate_to_words(s: str, n_words: int) -> str:
    if n_words <= 0:
        return ""
    parts = s.split()
    if len(parts) <= n_words:
        return s
    return " ".join(parts[:n_words]) + "…"


def truncate_to_word_cap(summary: InitialSummary, max_words: int = 1000) -> InitialSummary:
    """Return a copy of `summary` with each field proportionally trimmed
    so the total is ≤ max_words.

    Strategy: if total is already under cap, no-op. Otherwise scale every
    field's word allocation by (max_words / total). Lists items get
    pruned from the END if scaling them individually would yield empty
    items.
    """
    total = total_words(summary)
    if total <= max_words:
        return summary

    scale = max_words / total

    def cap_text(s: str) -> str:
        return _truncate_to_words(s, max(1, int(_word_count(s) * scale)))

    new_contribs: list[Contribution] = []
    for c in summary.key_contributions:
        t = cap_text(c.text)
        if t:
            new_contribs.append(Contribution(text=t, evidence_refs=c.evidence_refs))

    new_components: list[MethodComponent] = []
    for comp in summary.method.components:
        d = cap_text(comp.description)
        if d:
            new_components.append(
                MethodComponent(name=comp.name, description=d, evidence_refs=comp.evidence_refs)
            )

    new_findings: list[ExperimentFinding] = []
    for f in summary.experiments.key_findings:
        t = cap_text(f.text)
        if t:
            new_findings.append(ExperimentFinding(text=t, evidence_refs=f.evidence_refs))

    new_limits: list[str] = []
    for lim in summary.limitations:
        t = cap_text(lim)
        if t:
            new_limits.append(t)

    return InitialSummary(
        agent_id=summary.agent_id,
        tldr=cap_text(summary.tldr),
        core_idea=cap_text(summary.core_idea),
        key_contributions=new_contribs,
        method=MethodBlock(overview=cap_text(summary.method.overview), components=new_components),
        experiments=ExperimentsBlock(setup=cap_text(summary.experiments.setup), key_findings=new_findings),
        limitations=new_limits,
    )


def truncate_markdown_to_words(md: str, max_words: int = 1000) -> str:
    """Safety net for plain-markdown summaries (the baselines).

    Counts words by whitespace; truncates and appends an ellipsis. Tries
    to break on a sentence boundary near the cap.
    """
    parts = md.split()
    if len(parts) <= max_words:
        return md
    truncated = " ".join(parts[:max_words])
    # Try to back off to the previous '.' or '\n'
    boundary = max(truncated.rfind("."), truncated.rfind("\n"))
    if boundary > 0 and boundary > len(truncated) - 200:
        truncated = truncated[: boundary + 1]
    return truncated + "\n\n[…truncated to 1000-word cap…]"


__all__ = [
    "total_words",
    "truncate_to_word_cap",
    "truncate_markdown_to_words",
]
