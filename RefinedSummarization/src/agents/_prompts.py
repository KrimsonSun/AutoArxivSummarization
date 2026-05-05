"""Shared Jinja2 environment for agent prompt rendering."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

_PROMPTS_PATH = Path(__file__).resolve().parents[2] / "config" / "prompts.yaml"


@lru_cache(maxsize=1)
def _load_prompts() -> dict:
    with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
    )


def render(agent: str, slot: str, **ctx) -> str:
    """Render the ``{agent}.{slot}`` template (slot ∈ {'system', 'user'})."""
    prompts = _load_prompts()
    if agent not in prompts:
        raise KeyError(f"Unknown agent prompt: {agent}")
    if slot not in prompts[agent]:
        raise KeyError(f"Unknown slot {slot!r} for agent {agent!r}")
    template = _env().from_string(prompts[agent][slot])
    return template.render(**ctx)
