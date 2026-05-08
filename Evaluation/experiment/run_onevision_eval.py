"""Drive strict-LLM + DeBERTa-NLI evaluation on the n=15 OneVision experiment.

Wraps experiment.strict_reeval for the 15 papers we sampled with seed=42.
Both modes evaluate ALL methods present in summaries/<id>/ (Ours_onevision +
B1..B6) so we get full comparison data with one orchestrator.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from experiment.paper_pool import sample  # noqa: E402


async def _run_mode(config_path: str, papers: list[str]) -> int:
    cmd = [
        sys.executable, "-m", "experiment.strict_reeval",
        "--config", config_path,
        "--papers", *papers,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(EVAL_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    # Stream subprocess stdout to ours.
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        sys.stdout.write(line.decode())
        sys.stdout.flush()
    rc = await proc.wait()
    return rc


async def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    papers = sample(n, seed=seed)
    print(f"evaluating {len(papers)} papers under both judges: {papers}")

    print("\n========== STRICT-LLM mode ==========")
    rc1 = await _run_mode("config/strict.yaml", papers)
    print(f"strict_reeval exit={rc1}")

    print("\n========== DeBERTa-NLI mode ==========")
    rc2 = await _run_mode("config/deberta.yaml", papers)
    print(f"deberta_reeval exit={rc2}")

    print("\nDone. Run experiment/compare_onevision.py to aggregate.")


if __name__ == "__main__":
    asyncio.run(main())
