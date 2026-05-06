"""Small-scale v2 test on 7 papers — strict + DeBERTa evaluation only.

What v2 changes (already on disk in RefinedSummarization/config/prompts.yaml):
  - Refiner prompt: UNION-over-intersection (preserve every specific fact
    that appears in any of the 3 drafts; never silently drop a number /
    dataset / method name).
  - New IssueType.COVERAGE_GAP: verifier flags facts present in 1-2 of 3
    drafts as a positive signal for the refiner to preserve.
  - Verifier prompt teaches the new decision rule.

Workflow:
  1. Pick 7 papers (same seed=42 sample as Phase 1, so they're already cached).
  2. For each paper, invoke RefinedSummarization CLI to produce a fresh
     summary using the v2 prompts. Save to
     `outputs/experiment/summaries/<id>/Ours_v2.json`.
  3. Run strict_reeval (config/strict.yaml + config/deberta.yaml) which
     auto-picks up the new Ours_v2.json file, produces
     `Ours_v2.eval.json` next to the v1 `Ours.eval.json`.
  4. Compute paired v1-vs-v2 deltas on F1, recall, hallucination.

Cost: ~$1 OpenRouter, ~10 minutes wall-clock with concurrency=4.
Does NOT touch v1 baselines or v1 Ours summaries — strictly additive.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from experiment.paper_pool import sample


REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = Path(__file__).resolve().parents[1]
OUT = EVAL_ROOT / "outputs" / "experiment"
PAPERS_DIR = OUT / "papers"
SUMMARIES_DIR = OUT / "summaries"
REFINED_DIR = REPO_ROOT / "RefinedSummarization"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


async def generate_v2_summary(arxiv_id: str, sem: asyncio.Semaphore) -> Path | None:
    """Call RefinedSummarization CLI on paper, save as Ours_v2.json."""
    async with sem:
        sum_dir = SUMMARIES_DIR / arxiv_id
        sum_dir.mkdir(parents=True, exist_ok=True)
        out_json = sum_dir / "Ours_v2.json"
        if out_json.exists() and out_json.stat().st_size > 1000:
            log(f"  {arxiv_id}: Ours_v2.json already exists, skipping")
            return out_json

        pdf = PAPERS_DIR / f"{arxiv_id}.pdf"
        if not pdf.exists():
            log(f"  {arxiv_id}: PDF missing, skipping")
            return None

        log(f"  {arxiv_id}: running RefinedSummarization v2…")
        venv_py = REFINED_DIR / ".venv" / "bin" / "python"
        cmd = [
            str(venv_py), "-m", "src.cli",
            "--pdf", str(pdf),
            "--output-format", "json",
            "--skip-healthcheck",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(REFINED_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            log(f"  {arxiv_id}: RefinedSummarization failed (exit {proc.returncode})")
            log(f"    stderr tail: {stderr.decode()[-500:]}")
            return None
        out_json.write_bytes(stdout)
        log(f"  {arxiv_id}: ✓ Ours_v2.json written ({len(stdout)} bytes)")
        return out_json


async def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    paper_ids = sample(n, seed=seed)
    log(f"v2 test on {n} papers (seed={seed}): {paper_ids}")

    sem = asyncio.Semaphore(4)
    results = await asyncio.gather(
        *[generate_v2_summary(pid, sem) for pid in paper_ids],
        return_exceptions=False,
    )
    successes = [pid for pid, r in zip(paper_ids, results) if r is not None]
    log(f"DONE. {len(successes)}/{len(paper_ids)} v2 summaries generated.")
    log(f"Successful papers: {successes}")
    log("")
    log("Next steps (manual):")
    log("  python -m experiment.strict_reeval --config config/strict.yaml --papers " + " ".join(successes))
    log("  python -m experiment.strict_reeval --config config/deberta.yaml --papers " + " ".join(successes))
    log("  python -m experiment.compare_v1_v2")


if __name__ == "__main__":
    asyncio.run(main())
