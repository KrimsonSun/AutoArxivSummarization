"""Strict-mode re-evaluation of summaries already produced by experiment/run.py.

Reads the same summary cache (outputs/experiment/summaries/<id>/<method>.{json,md})
and writes strict reports to outputs/experiment/evals_strict/<id>/<method>.eval.json.

Critical fairness guarantee: paper claims are extracted ONCE per paper and
cached at outputs/experiment/paper_claims/<id>.json. All 6 summaries on the
same paper are scored against the SAME claim list, so paper_total_claims is
constant across methods within a paper.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from src.config_loader import load_config
from src.paper_chunker import parse_paper
from src.pipeline import EvaluationPipeline
from src.schemas import PaperClaim


EVAL_ROOT = Path(__file__).resolve().parents[1]
OUT = EVAL_ROOT / "outputs" / "experiment"
PAPERS_DIR = OUT / "papers"
SUMMARIES_DIR = OUT / "summaries"
PAPER_CLAIMS_DIR = OUT / "paper_claims"
# Output directory varies per config — set in main() via --output-suffix.


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


async def get_or_extract_paper_claims(
    pipeline: EvaluationPipeline, arxiv_id: str
) -> list[PaperClaim]:
    """Cache paper claims to disk so all 6 summaries score against the same set."""
    PAPER_CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    cache = PAPER_CLAIMS_DIR / f"{arxiv_id}.json"
    if cache.exists() and cache.stat().st_size > 200:
        data = json.loads(cache.read_text())
        return [PaperClaim.model_validate(c) for c in data["claims"]]

    pdf = PAPERS_DIR / f"{arxiv_id}.pdf"
    log(f"  extracting paper claims (one-time)…")
    claims = await pipeline.extract_paper_claims(pdf)
    cache.write_text(
        json.dumps({"claims": [c.model_dump() for c in claims]}, indent=2)
    )
    log(f"  cached {len(claims)} paper claims → {cache}")
    return claims


async def reeval_one_paper(
    arxiv_id: str,
    pipeline: EvaluationPipeline,
    evals_dir_root: Path,
) -> dict:
    log(f"=== {arxiv_id} (re-eval → {evals_dir_root.name}) ===")
    pdf = PAPERS_DIR / f"{arxiv_id}.pdf"
    if not pdf.exists():
        log(f"  PDF missing for {arxiv_id}, skipping")
        return {}

    sum_dir = SUMMARIES_DIR / arxiv_id
    if not sum_dir.exists():
        log(f"  no summaries cached for {arxiv_id}, skipping")
        return {}

    eval_dir = evals_dir_root / arxiv_id
    eval_dir.mkdir(parents=True, exist_ok=True)

    # 1) Get the SHARED paper claim list for this paper.
    paper_claims = await get_or_extract_paper_claims(pipeline, arxiv_id)
    if not paper_claims:
        log(f"  zero paper claims extracted, skipping")
        return {}

    # 2) Find every summary file for this paper.
    # Skip *.voting.json files — those are voter transcripts emitted alongside
    # the OneVision summary (e.g. Ours_onevision_v3.voting.json) and must not
    # be evaluated as if they were summaries.
    summary_files: list[tuple[str, Path]] = []
    for p in sorted(sum_dir.iterdir()):
        if p.name.endswith(".voting.json"):
            continue
        if p.suffix == ".json":
            method = p.stem  # "Ours"
            summary_files.append((method, p))
        elif p.suffix == ".md":
            method = p.stem  # "B1_llama_naive"
            summary_files.append((method, p))

    out: dict[str, str] = {}
    for method, summary_path in summary_files:
        eval_json = eval_dir / f"{method}.eval.json"
        if eval_json.exists() and eval_json.stat().st_size > 500:
            try:
                d = json.loads(eval_json.read_text())
                if not d.get("error"):
                    log(f"  cached strict {method}.eval.json")
                    out[method] = str(eval_json)
                    continue
            except json.JSONDecodeError:
                pass

        log(f"  strict-evaluating {method}…")
        try:
            report = await pipeline.run(summary_path, pdf, paper_claims=paper_claims)
            eval_json.write_text(report.model_dump_json(indent=2))
            log(
                f"    {method}: precision={report.evidence_coverage:.3f}  "
                f"recall={report.paper_recall:.3f}  F1={report.f1:.3f}  "
                f"hal={report.hallucination_rate:.3f}"
            )
            out[method] = str(eval_json)
        except Exception as e:
            log(f"    {method} FAILED: {type(e).__name__}: {e}")
            err_payload = {
                "error": True, "type": type(e).__name__, "message": str(e),
                "method": method, "arxiv_id": arxiv_id,
            }
            eval_json.write_text(json.dumps(err_payload, indent=2))
            out[method] = str(eval_json)
    return out


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/strict.yaml",
        help="Path to eval config. Use config/strict.yaml (LLM-judge) or "
             "config/deberta.yaml (DeBERTa-NLI).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output dir name under outputs/experiment/. "
             "Defaults: 'evals_strict' for strict.yaml, 'evals_deberta' for deberta.yaml.",
    )
    parser.add_argument(
        "--papers",
        nargs="*",
        default=None,
        help="Optional list of arxiv IDs to re-evaluate (default: all available).",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if not config.scoring.strict_mode:
        log("ERROR: config has strict_mode=false; use a config with strict_mode=true")
        sys.exit(1)

    # Default output dir based on verifier kind.
    if args.output_dir:
        evals_root = OUT / args.output_dir
    elif config.scoring.verifier_kind == "deberta_nli":
        evals_root = OUT / "evals_deberta"
    else:
        evals_root = OUT / "evals_strict"

    log(f"Loading pipeline from {args.config} (verifier={config.scoring.verifier_kind})")
    pipeline = EvaluationPipeline(config)

    if not SUMMARIES_DIR.exists():
        log(f"No summaries directory at {SUMMARIES_DIR}")
        sys.exit(1)
    paper_ids = sorted(
        p.name for p in SUMMARIES_DIR.iterdir()
        if p.is_dir() and any(p.iterdir())
    )
    if args.papers:
        paper_ids = [pid for pid in paper_ids if pid in args.papers]

    # Concurrency: process N papers in parallel, bounded by a semaphore.
    # OpenRouter paid tier handles 4x parallel comfortably. Each paper makes
    # ~10–15 LLM calls so 4 concurrent papers ≈ ~50 in-flight requests max,
    # well within rate limits. Override with EVAL_CONCURRENCY env var if needed.
    import os
    concurrency = int(os.environ.get("EVAL_CONCURRENCY", "8"))
    sem = asyncio.Semaphore(concurrency)

    log(f"Re-eval on {len(paper_ids)} papers → {evals_root} (concurrency={concurrency})")

    async def _bounded(pid: str):
        async with sem:
            try:
                await reeval_one_paper(pid, pipeline, evals_root)
            except Exception as e:
                log(f"!!! {pid} crashed: {type(e).__name__}: {e}")

    await asyncio.gather(*[_bounded(pid) for pid in paper_ids])
    log("DONE")


if __name__ == "__main__":
    asyncio.run(main())
