"""End-to-end demo (handoff §12 acceptance criterion).

Usage:
    python examples/run_example.py [pdf_path]

Defaults to tests/fixtures/sample_paper.pdf if no path is given.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from src.config.loader import load_config
from src.pipeline import DebatePipeline
from src.postprocessing.markdown_formatter import to_markdown
from src.utils.logging import configure_logging


async def amain(pdf_path: str) -> None:
    config = load_config("config/default.yaml")
    configure_logging(level="INFO", json_logs=False)
    pipeline = DebatePipeline(config)
    await pipeline.healthcheck()
    result = await pipeline.run(Path(pdf_path))

    project_root = Path(__file__).resolve().parents[1]
    out_dir = project_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    fname = result.metadata.arxiv_id or "demo"
    (out_dir / f"{fname}.json").write_text(result.model_dump_json(indent=2))
    (out_dir / f"{fname}.md").write_text(to_markdown(result))
    print(f"\nWrote outputs/{fname}.json and outputs/{fname}.md")


def main() -> None:
    pdf = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/sample_paper.pdf"
    asyncio.run(amain(pdf))


if __name__ == "__main__":
    main()
