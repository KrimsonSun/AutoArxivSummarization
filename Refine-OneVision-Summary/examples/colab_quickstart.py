"""Colab-friendly quickstart.

Paste each section into separate Colab cells, OR run the file directly:

    !python examples/colab_quickstart.py YOUR_OPENROUTER_KEY [arxiv_id]

The script:
  1. Sets OPENAI_API_KEY + OPENAI_BASE_URL for OpenRouter
  2. Downloads an arXiv PDF (default: 1706.03762 = Attention Is All You Need)
  3. Runs the full debate pipeline
  4. Prints the FinalSummary JSON + Markdown
  5. Saves outputs/<arxiv_id>.{json,md}

No GPU needed — every LLM call goes to OpenRouter.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------- Cell 1: install
# In a Colab cell, run:
#   !git clone <your repo> && cd RefinedSummarization
#   !pip install -e ".[dev]"
# (uncomment below if you want this script to do it for you)
# subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], check=True)


# ---------------------------------------------------------------- Cell 2: env
def setup_env(openrouter_key: str) -> None:
    """OpenRouter requires only ONE key for all 3 heterogeneous open-source models."""
    os.environ["OPENAI_API_KEY"] = openrouter_key
    os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
    os.environ["DEV_MODE"] = "0"


# ---------------------------------------------------------------- Cell 3: fetch paper
def fetch_arxiv(arxiv_id: str, dest: Path) -> Path:
    import urllib.request
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}", file=sys.stderr)
    urllib.request.urlretrieve(url, dest)
    return dest


# ---------------------------------------------------------------- Cell 4: run pipeline
async def run_pipeline(pdf_path: Path) -> None:
    # Imports done here so env vars are set before LLM clients init.
    from src.config.loader import load_config
    from src.pipeline import DebatePipeline
    from src.postprocessing.markdown_formatter import to_markdown
    from src.utils.logging import configure_logging

    configure_logging(level="INFO", json_logs=False)
    config = load_config("config/default.yaml")
    pipeline = DebatePipeline(config)

    print(">>> Healthcheck (pinging OpenRouter)...", file=sys.stderr)
    health = await pipeline.healthcheck()
    print(f"    {health}", file=sys.stderr)
    if not all(health.values()):
        print("ERROR: healthcheck failed. Check your OpenRouter key.", file=sys.stderr)
        sys.exit(1)

    print(">>> Running debate pipeline...", file=sys.stderr)
    result = await pipeline.run(pdf_path)

    # Save
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fname = result.metadata.arxiv_id or pdf_path.stem
    (out_dir / f"{fname}.json").write_text(result.model_dump_json(indent=2))
    (out_dir / f"{fname}.md").write_text(to_markdown(result))

    # Display
    print("\n" + "=" * 70)
    print(to_markdown(result))
    print("=" * 70)
    print(f"\nSaved: outputs/{fname}.json + outputs/{fname}.md")
    print(
        f"\nTokens used (across all LLM calls): "
        f"prompt={result.metadata.total_tokens_used['prompt']}  "
        f"completion={result.metadata.total_tokens_used['completion']}"
    )


# ---------------------------------------------------------------- Main
def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python examples/colab_quickstart.py <openrouter_key> [arxiv_id]",
            file=sys.stderr,
        )
        sys.exit(2)
    openrouter_key = sys.argv[1]
    arxiv_id = sys.argv[2] if len(sys.argv) > 2 else "1706.03762"

    setup_env(openrouter_key)
    pdf_path = fetch_arxiv(arxiv_id, Path(f"tests/fixtures/{arxiv_id}.pdf"))
    asyncio.run(run_pipeline(pdf_path))


if __name__ == "__main__":
    main()
