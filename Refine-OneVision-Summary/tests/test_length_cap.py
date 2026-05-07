"""Unit tests for the 1000-word post-hoc cap."""
from __future__ import annotations

from src.postprocessing.length_cap import (
    total_words,
    truncate_markdown_to_words,
    truncate_to_word_cap,
)
from src.schemas.summary import (
    Contribution,
    ExperimentFinding,
    ExperimentsBlock,
    InitialSummary,
    MethodBlock,
    MethodComponent,
)


def _summary(words_per_field: int) -> InitialSummary:
    blob = " ".join(["word"] * words_per_field)
    return InitialSummary(
        agent_id="X",
        tldr=blob,
        core_idea=blob,
        key_contributions=[Contribution(text=blob)],
        method=MethodBlock(
            overview=blob,
            components=[MethodComponent(name="C1", description=blob)],
        ),
        experiments=ExperimentsBlock(
            setup=blob, key_findings=[ExperimentFinding(text=blob)]
        ),
        limitations=[blob],
    )


def test_under_cap_is_no_op():
    s = _summary(words_per_field=50)
    capped = truncate_to_word_cap(s, max_words=10000)
    assert s.tldr == capped.tldr


def test_over_cap_gets_proportionally_trimmed():
    s = _summary(words_per_field=500)  # 8 fields × 500 ≈ 4000 words
    capped = truncate_to_word_cap(s, max_words=1000)
    assert total_words(capped) <= 1100  # Some slack for rounding + final char.


def test_markdown_truncation_emits_marker():
    md = " ".join([f"w{i}" for i in range(2000)])
    out = truncate_markdown_to_words(md, max_words=1000)
    assert "[…truncated to 1000-word cap…]" in out
    # Word count of the prefix should be ≤ 1000.
    prefix = out.split("[…")[0]
    assert len(prefix.split()) <= 1010
