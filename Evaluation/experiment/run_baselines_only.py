"""Run B1-B6 baseline summarisers on the 29 cached papers.

The OneVision n=29 run already downloaded PDFs to outputs/experiment/papers/
and produced Ours_onevision_v3.json under summaries/<id>/. This driver fills
in the 6 baseline .md files alongside each Ours_onevision_v3.json so
strict_reeval can pick them all up.

Skips per-paper baselines that are already cached; safe to re-run.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from experiment.baselines import BASELINES, run_all_baselines
from src.paper_chunker import parse_paper

OUT = EVAL_ROOT / "outputs" / "experiment"
PAPERS_DIR = OUT / "papers"
SUMMARIES_DIR = OUT / "summaries"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def run_baselines_for(arxiv_id: str) -> dict:
    pdf = PAPERS_DIR / f"{arxiv_id}.pdf"
    if not pdf.exists():
        return {"arxiv_id": arxiv_id, "error": "pdf missing"}
    sum_dir = SUMMARIES_DIR / arxiv_id
    sum_dir.mkdir(parents=True, exist_ok=True)

    pending: list[str] = []
    for spec in BASELINES:
        out_md = sum_dir / f"{spec.name}.md"
        if out_md.exists() and out_md.stat().st_size > 200:
            continue
        pending.append(spec.name)

    if not pending:
        log(f"  {arxiv_id}: all 6 baselines cached")
        return {"arxiv_id": arxiv_id, "wrote": 0, "cached": len(BASELINES)}

    try:
        paper = parse_paper(pdf)
        paper_text = "\n\n".join(p.text for p in paper.paragraphs)
        title = paper.title or arxiv_id
    except Exception as e:
        log(f"  {arxiv_id}: parse failed — {type(e).__name__}: {str(e)[:200]}")
        return {"arxiv_id": arxiv_id, "error": f"parse: {type(e).__name__}"}

    log(f"  {arxiv_id}: running {len(pending)} pending baselines: {pending}")
    try:
        results = await run_all_baselines(paper_text, title)
    except Exception as e:
        log(f"  {arxiv_id}: baseline run failed — {type(e).__name__}: {str(e)[:200]}")
        return {"arxiv_id": arxiv_id, "error": f"baselines: {type(e).__name__}"}
    written = 0
    for spec_name, md in results.items():
        out_md = sum_dir / f"{spec_name}.md"
        if out_md.exists() and out_md.stat().st_size > 200:
            continue
        out_md.write_text(md)
        written += 1
    log(f"  {arxiv_id}: wrote {written} baseline files")
    return {"arxiv_id": arxiv_id, "wrote": written}


async def main() -> int:
    paper_ids = sorted(p.name for p in SUMMARIES_DIR.iterdir() if p.is_dir())
    # Filter to those with a Ours_onevision_v3.json — only n=29 papers we ran.
    valid = []
    for pid in paper_ids:
        if (SUMMARIES_DIR / pid / "Ours_onevision_v3.json").exists():
            valid.append(pid)
    log(f"running baselines on {len(valid)} papers")

    concurrency = int(os.environ.get("EXPERIMENT_CONCURRENCY", "3"))
    sem = asyncio.Semaphore(concurrency)

    async def _gated(pid: str) -> dict:
        async with sem:
            return await run_baselines_for(pid)

    t0 = time.monotonic()
    results = await asyncio.gather(*[_gated(pid) for pid in valid])
    elapsed = time.monotonic() - t0
    n_err = sum(1 for r in results if "error" in r)
    n_wrote = sum(r.get("wrote", 0) for r in results)
    log(f"done; {len(valid) - n_err} OK, {n_err} errors, {n_wrote} files written, {elapsed/60:.1f} min wall")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
