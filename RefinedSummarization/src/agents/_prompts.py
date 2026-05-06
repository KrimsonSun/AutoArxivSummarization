"""Shared Jinja2 environment for agent prompt rendering.

Open-source models on OpenRouter (Llama / Qwen / DeepSeek) do NOT reliably
follow free-form schema instructions — they freelance with extra wrapper
fields like {"summary": {...}} or arrays at top level. The fix is to
inject a concrete JSON example block into every system prompt so the
model sees the exact required shape. We render the example automatically
from the Pydantic schema's expected fields.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Type

import yaml
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel

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


# ----------------------------------------------------- schema → example block

def schema_example_block(schema_class: Type[BaseModel]) -> str:
    """Render a Markdown code block with the exact JSON shape the LLM must produce.

    We use a *concrete example* rather than the raw JSON schema because LLMs
    follow examples much more reliably than they follow JSON Schema specs.
    Each field gets a placeholder string / list so the model sees structure
    AND the kind of content expected.
    """
    example = _build_example(schema_class)
    return (
        "**Required JSON output shape (match EXACTLY — no wrapper objects, no extra keys):**\n\n"
        "```json\n"
        + json.dumps(example, indent=2, ensure_ascii=False)
        + "\n```"
    )


def _build_example(model: Type[BaseModel]) -> dict:
    """Recursively materialise an example instance from a Pydantic model."""
    schema = model.model_json_schema()
    return _walk(schema, schema.get("$defs", {}))


def _walk(node: dict, defs: dict) -> object:
    # Resolve $ref
    if "$ref" in node:
        ref_name = node["$ref"].split("/")[-1]
        return _walk(defs[ref_name], defs)
    # anyOf / oneOf — pick first non-null
    if "anyOf" in node:
        non_null = [s for s in node["anyOf"] if s.get("type") != "null"]
        return _walk(non_null[0] if non_null else node["anyOf"][0], defs)
    t = node.get("type")
    if t == "object":
        out = {}
        for fname, fnode in (node.get("properties") or {}).items():
            out[fname] = _walk(fnode, defs)
        return out
    if t == "array":
        items = node.get("items", {"type": "string"})
        return [_walk(items, defs)]
    if t == "string":
        if "enum" in node:
            return node["enum"][0]
        if "pattern" in node:
            p = node["pattern"]
            if p.startswith("^P"):
                return "P1"
            if p.startswith("^I"):
                return "I1"
            if p.startswith("^C"):
                return "C1"
        return "<string>"
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return False
    return None
