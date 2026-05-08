"""5 single-call baseline summarizers + spec for our method.

Each baseline is one LLM call producing plain Markdown — Evaluation accepts
.md / .txt directly so we can run the same evaluator across all summaries.

Variables we want to isolate:
  B1, B2, B3 — different model identities (Llama / Qwen / DeepSeek), same naive prompt
               → tests whether multi-LLM debate beats any single one
  B4         — same family, much smaller (Llama 3.1 8B)
               → cost/quality lower bound (sanity check)
  B5         — same model as B1, structured prompt (sectioned)
               → isolates "our pipeline architecture" from "good prompt engineering"
  Ours       — full RefinedSummarization pipeline (handled separately)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.llm_client import LLMClient


@dataclass
class BaselineSpec:
    name: str       # short slug, used in filenames + chart labels
    model: str
    prompt_kind: str  # "naive" | "structured"


BASELINES: list[BaselineSpec] = [
    BaselineSpec("B1_llama_naive",     "meta-llama/llama-3.3-70b-instruct", "naive"),
    BaselineSpec("B2_qwen_naive",      "qwen/qwen-2.5-72b-instruct",        "naive"),
    BaselineSpec("B3_deepseek_naive",  "deepseek/deepseek-chat",            "naive"),
    BaselineSpec("B4_llama8b_naive",   "meta-llama/llama-3.1-8b-instruct",  "naive"),
    BaselineSpec("B5_llama_structured","meta-llama/llama-3.3-70b-instruct", "structured"),
    # ----- B6: ablation control for "is the v2 win prompt-engineering or architecture?" -----
    # Same Llama-70B backbone as B1/B5 but with the v2 union-bias prompt directly
    # applied at single-call summarisation time. If B6 ≈ Ours_v2, then the v2
    # gain is prompt engineering, not multi-agent architecture. If B6 << Ours_v2,
    # then the 3-LLM debate matters (v2 refiner prompt is necessary but not
    # sufficient).
    BaselineSpec("B6_llama_v2prompt",  "meta-llama/llama-3.3-70b-instruct", "v2_inspired"),
]


# ---------------------------------------------------------------- prompts

_NAIVE_SYSTEM = (
    "You are a senior researcher. Summarize the academic paper provided in "
    "concise, faithful Markdown. Stick to facts in the paper — do not "
    "speculate or add information that isn't there. Target length: "
    "approximately 800-1000 words (hard cap: 1000 words)."
)

_STRUCTURED_SYSTEM = (
    "You are a senior researcher writing a structured summary of an academic "
    "paper. Use the exact 5 sections below in Markdown. Be specific and "
    "quantitative. Do NOT introduce facts not in the paper. "
    "Target length: approximately 800-1000 words total (hard cap: 1000).\n\n"
    "## TL;DR\n(one paragraph, ≤ 5 sentences)\n\n"
    "## Key Contributions\n(bulleted list of 3–5 atomic contributions)\n\n"
    "## Method\n(how the system works — 2–3 paragraphs)\n\n"
    "## Experiments\n(setup + key quantitative findings — 2–3 paragraphs)\n\n"
    "## Limitations\n(bulleted list of 2–4 limitations stated by the authors)"
)

# B6: single-LLM ablation control adapted from the v2 refiner prompt
# (RefinedSummarization/config/prompts.yaml).
# Drop the "merge from 3 drafts" framing (no drafts in single-call setting),
# keep every other UNION-bias / specificity-over-abstraction directive.
# This is the prompt-engineering control: same backbone as B1/B5, but with
# union-bias instructions explicitly written into the prompt.
_V2_INSPIRED_SYSTEM = (
    "You are a senior researcher producing a comprehensive structured "
    "summary of an academic paper. Your goal is to PRESERVE every "
    "specific fact (number, dataset, method name, quantitative finding) "
    "from the paper.\n\n"
    "Common failure modes to avoid:\n"
    "-  Replacing \"achieves 28.4 BLEU on WMT 2014 EN-DE\" with \"achieves "
    "state-of-the-art\".\n"
    "-  Dropping a method component because it's a detail.\n"
    "-  Smoothing specific claims into generic paraphrases.\n\n"
    "Concretely:\n"
    "-  Specific numerics (BLEU/F1/accuracy/dataset sizes) → ALWAYS keep.\n"
    "-  Named components, datasets, baselines → ALWAYS keep.\n"
    "-  Concrete experimental findings → ALWAYS keep.\n"
    "-  Stated limitations → ALWAYS keep.\n"
    "-  Abstract framing → use the clearest single phrasing.\n\n"
    "Rules:\n"
    "1. PREFER specificity over abstraction: \"achieves 28.4 BLEU\" beats "
    "\"achieves SOTA\"; \"uses 6 encoder layers\" beats \"uses multiple "
    "layers\".\n"
    "2. Aim for higher fact density: each non-trivial sentence should add "
    "a specific verifiable fact.\n"
    "3. Do NOT introduce claims that aren't in the paper.\n"
    "4. Target length: approximately 800-1000 words total (hard cap: 1000).\n"
    "5. Use Markdown formatting. Use 5 sections:\n\n"
    "## TL;DR\n(one paragraph, ≤ 5 sentences, with specific numbers/names)\n\n"
    "## Key Contributions\n(bulleted list of 3–5 atomic contributions)\n\n"
    "## Method\n(how the system works — 2–3 paragraphs)\n\n"
    "## Experiments\n(setup + key quantitative findings — 2–3 paragraphs, "
    "include all major numerical results)\n\n"
    "## Limitations\n(bulleted list of 2–4 limitations stated by authors)"
)


def system_prompt_for(spec: BaselineSpec) -> str:
    if spec.prompt_kind == "v2_inspired":
        return _V2_INSPIRED_SYSTEM
    if spec.prompt_kind == "structured":
        return _STRUCTURED_SYSTEM
    return _NAIVE_SYSTEM


# ------------------------------------------------------- the actual call

async def run_baseline(
    spec: BaselineSpec,
    paper_text: str,
    title: str,
) -> str:
    """One LLM call, return the Markdown summary string."""
    # Trim very long papers to keep the call within context budget.
    # Llama 3.3 70B has 128k context, but stay safe at ~60k chars (~15k tokens).
    if len(paper_text) > 60_000:
        paper_text = paper_text[:60_000] + "\n\n[...paper truncated for context...]"

    client = LLMClient(
        model=spec.model,
        temperature=0.3,
        max_tokens=2200,
    )
    system = system_prompt_for(spec)
    user = (
        f"Paper title: {title}\n\nPaper content:\n\n{paper_text}\n\n"
        f"Write the summary now. Target length: 800-1000 words, hard cap 1000."
    )

    # We bypass the structured-output JSON path because baselines emit plain
    # text. Use the underlying SDK directly to get raw text.
    try:
        r = await client._client.chat.completions.create(
            model=spec.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        text = (r.choices[0].message.content or "").strip()
        # Some models still wrap in code fences — just strip if present.
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        # Track usage on the client for cost reporting.
        usage = getattr(r, "usage", None)
        if usage is not None:
            client.usage.add(
                getattr(usage, "prompt_tokens", 0) or 0,
                getattr(usage, "completion_tokens", 0) or 0,
            )
        # Hard 1000-word cap (post-hoc safety for any model that overshoots).
        words = text.split()
        if len(words) > 1000:
            head = " ".join(words[:1000])
            # Try to back off to a sentence boundary near the cap.
            boundary = max(head.rfind("."), head.rfind("\n"))
            if boundary > 0 and boundary > len(head) - 200:
                head = head[: boundary + 1]
            text = head + "\n\n[…truncated to 1000-word cap…]"
        return text
    finally:
        # Don't leave an open httpx pool around.
        try:
            await client._client.close()
        except Exception:
            pass


async def run_all_baselines(
    paper_text: str,
    title: str,
) -> dict[str, str]:
    """Run the 5 baselines in parallel. Returns {baseline_name: markdown}."""
    results = await asyncio.gather(
        *[run_baseline(spec, paper_text, title) for spec in BASELINES],
        return_exceptions=True,
    )
    out: dict[str, str] = {}
    for spec, r in zip(BASELINES, results):
        if isinstance(r, Exception):
            out[spec.name] = f"# Baseline Failed\nError: {r}"
        else:
            out[spec.name] = r
    return out
