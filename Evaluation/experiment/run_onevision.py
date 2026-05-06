"""Run the OneVision pipeline on n=15 papers + evaluate.

Mirrors experiment/run.py's caching layout but targets the new
Refine-OneVision-Summary pipeline. Steps:

  1. Sample N=15 papers (seed=42), download PDFs.
  2. For each paper: run OneVisionPipeline → write
     outputs/experiment/summaries/<id>/Ours_onevision.json
     and the voting transcript to
     outputs/experiment/summaries/<id>/Ours_onevision.voting.json
  3. Also (re-)run baselines B1, B2, B6 with the 1000-word cap so they're
     length-comparable. Skip if already cached.
  4. Run strict + deberta evaluation across all methods on these 15
     papers. F0.5 is now reported alongside F1 in every report.

Usage:
  cd Evaluation
  EXPERIMENT_CONCURRENCY=4 .venv/bin/python -m experiment.run_onevision

Cost target: ~$8-12, ~25 minutes wall.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Both packages live as siblings of the cwd; make sure src/ resolves correctly
# in the evaluator's process by running this from Evaluation/.
EVAL_ROOT = Path(__file__).resolve().parents[1]
ONEVISION_ROOT = EVAL_ROOT.parent / "Refine-OneVision-Summary"

OUT = EVAL_ROOT / "outputs" / "experiment"
PAPERS_DIR = OUT / "papers"
SUMMARIES_DIR = OUT / "summaries"
OUT.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# Reuse the existing paper-pool sampler.
sys.path.insert(0, str(EVAL_ROOT))
from experiment.paper_pool import sample  # noqa: E402
from experiment.run import download_paper, run_baselines_for_paper, evaluate_summaries  # noqa: E402


# ---------------------------------------------------------------------------
# OneVision pipeline driver — invokes the OneVision package via subprocess
# venv to avoid any cross-package dependency conflicts.

ONEVISION_VENV_PY = ONEVISION_ROOT / ".venv" / "bin" / "python"


async def run_onevision(pdf_path: Path, arxiv_id: str) -> Path:
    """Run the OneVision pipeline on the PDF, return path to written JSON."""
    sum_dir = SUMMARIES_DIR / arxiv_id
    sum_dir.mkdir(parents=True, exist_ok=True)
    out_json = sum_dir / "Ours_onevision.json"
    out_vote = sum_dir / "Ours_onevision.voting.json"

    if out_json.exists() and out_json.stat().st_size > 1000:
        log(f"  cached Ours_onevision.json")
        return out_json

    if not ONEVISION_VENV_PY.exists():
        raise RuntimeError(
            f"OneVision venv not built at {ONEVISION_VENV_PY}. "
            "Run: cd ../Refine-OneVision-Summary && python3 -m venv .venv && "
            ".venv/bin/pip install -e '.[dev]'"
        )

    cmd = [
        str(ONEVISION_VENV_PY),
        "-m", "src.cli",
        "--pdf", str(pdf_path),
        "--config", "config/default.yaml",
        "--skip-healthcheck",
        "--out", str(out_json),
    ]
    log(f"  running OneVision on {arxiv_id}…")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(ONEVISION_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        log(f"  OneVision FAILED for {arxiv_id}:\n{stderr.decode()[-2000:]}")
        # Write an error stub so we don't retry forever.
        out_json.write_text(json.dumps({"error": True, "stderr": stderr.decode()[-2000:]}, indent=2))
    else:
        log(f"  OneVision OK for {arxiv_id}")
    return out_json


# ---------------------------------------------------------------------------

async def process_one_paper(arxiv_id: str) -> dict[str, Path]:
    log(f"=== {arxiv_id} ===")
    pdf = download_paper(arxiv_id)
    summary_paths: dict[str, Path] = {}

    # OneVision summary.
    summary_paths["Ours_onevision"] = await run_onevision(pdf, arxiv_id)
    # Reuse baselines (B1..B6) — generates only what's not cached.
    bp = await run_baselines_for_paper(pdf, arxiv_id)
    summary_paths.update(bp)
    return summary_paths


async def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    paper_ids = sample(n, seed=seed)
    log(f"sampled {len(paper_ids)} papers (seed={seed}): {paper_ids}")

    concurrency = int(os.environ.get("EXPERIMENT_CONCURRENCY", "4"))
    sem = asyncio.Semaphore(concurrency)

    async def _gated(pid: str) -> None:
        async with sem:
            await process_one_paper(pid)

    await asyncio.gather(*[_gated(pid) for pid in paper_ids])
    log("all papers processed")

    # Defer evaluation to experiment.strict_reeval so the user can inspect
    # the OneVision summaries before paying for evaluator LLM calls.
    log("\nNext step (manual):")
    log("  EVAL_CONCURRENCY=4 .venv/bin/python -m experiment.strict_reeval \\")
    log("      --config config/strict.yaml --papers " + " ".join(paper_ids))
    log("  EVAL_CONCURRENCY=4 .venv/bin/python -m experiment.strict_reeval \\")
    log("      --config config/deberta.yaml --papers " + " ".join(paper_ids))


if __name__ == "__main__":
    asyncio.run(main())
