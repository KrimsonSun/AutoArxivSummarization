"""End-to-end experiment orchestrator.

For each of N sampled papers:
  1. Download PDF (cached to outputs/experiment/papers/<id>.pdf)
  2. Run RefinedSummarization (subprocess) → outputs/experiment/summaries/<id>/ours.json
  3. Run 5 baseline summarizers (parallel async) → .../summaries/<id>/<baseline>.md
  4. Run Evaluation on each summary (Ours + 5 baselines) → .../evals/<id>/<method>.json

Skip-if-exists at every step so re-running picks up where it left off.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from experiment.baselines import BASELINES, run_all_baselines
from experiment.paper_pool import sample
from src.config_loader import load_config
from src.paper_chunker import parse_paper
from src.pipeline import EvaluationPipeline


# --------------------------------------------------- paths

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = Path(__file__).resolve().parents[1]
OUT = EVAL_ROOT / "outputs" / "experiment"
PAPERS_DIR = OUT / "papers"
SUMMARIES_DIR = OUT / "summaries"
EVALS_DIR = OUT / "evals"

REFINED_DIR = REPO_ROOT / "RefinedSummarization"


# --------------------------------------------------- helpers

def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def download_paper(arxiv_id: str) -> Path:
    """Cache PDF at outputs/experiment/papers/<id>.pdf."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    dest = PAPERS_DIR / f"{arxiv_id}.pdf"
    if dest.exists() and dest.stat().st_size > 50_000:
        return dest
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    log(f"  downloading {url}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "RefinedSummarization-Eval/1.0 (research)"},
    )
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def run_refined_summarization(pdf_path: Path, arxiv_id: str) -> Path:
    """Subprocess call to RefinedSummarization CLI. Returns path to FinalSummary JSON."""
    sum_dir = SUMMARIES_DIR / arxiv_id
    sum_dir.mkdir(parents=True, exist_ok=True)
    out_json = sum_dir / "Ours.json"  # capital O matches METHOD_ORDER in plot.py
    if out_json.exists() and out_json.stat().st_size > 1000:
        log(f"  cached ours.json")
        return out_json

    log(f"  running RefinedSummarization (3-LLM debate)…")
    venv_py = REFINED_DIR / ".venv" / "bin" / "python"
    if not venv_py.exists():
        raise FileNotFoundError(
            f"RefinedSummarization venv not found at {venv_py}. "
            "Run: cd RefinedSummarization && python3 -m venv .venv && pip install -e '.[dev]'"
        )

    cmd = [
        str(venv_py), "-m", "src.cli",
        "--pdf", str(pdf_path),
        "--output-format", "json",
        "--skip-healthcheck",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REFINED_DIR),
        capture_output=True,
        text=True,
        timeout=900,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"RefinedSummarization failed (exit={proc.returncode})\n"
            f"stderr tail:\n{proc.stderr[-2000:]}"
        )
    # The CLI's stdout is the JSON itself (per --output-format json).
    out_json.write_text(proc.stdout)
    return out_json


async def run_baselines_for_paper(pdf_path: Path, arxiv_id: str) -> dict[str, Path]:
    """Run the 5 single-call baselines on the paper, save each as .md."""
    sum_dir = SUMMARIES_DIR / arxiv_id
    sum_dir.mkdir(parents=True, exist_ok=True)

    # Prepare paper text once (shared across baselines).
    paper = parse_paper(pdf_path)
    paper_text = "\n\n".join(p.text for p in paper.paragraphs)
    title = paper.title

    paths: dict[str, Path] = {}
    pending: list[str] = []
    for spec in BASELINES:
        out_md = sum_dir / f"{spec.name}.md"
        if out_md.exists() and out_md.stat().st_size > 200:
            paths[spec.name] = out_md
        else:
            pending.append(spec.name)

    if pending:
        log(f"  running {len(pending)} baselines: {pending}")
        results = await run_all_baselines(paper_text, title)
        for spec_name, md in results.items():
            out_md = sum_dir / f"{spec_name}.md"
            if not out_md.exists() or out_md.stat().st_size <= 200:
                out_md.write_text(md)
            paths[spec_name] = out_md
    else:
        log(f"  cached all 5 baselines")

    return paths


async def evaluate_summaries(
    arxiv_id: str,
    pdf_path: Path,
    summary_paths: dict[str, Path],
) -> dict[str, Path]:
    """Run Evaluation on every summary. Returns {method_name: eval_json_path}."""
    eval_dir = EVALS_DIR / arxiv_id
    eval_dir.mkdir(parents=True, exist_ok=True)

    config = load_config("config/default.yaml")
    pipeline = EvaluationPipeline(config)

    out: dict[str, Path] = {}
    for method_name, summary_path in summary_paths.items():
        eval_json = eval_dir / f"{method_name}.eval.json"
        if eval_json.exists() and eval_json.stat().st_size > 500:
            out[method_name] = eval_json
            continue
        log(f"  evaluating {method_name}…")
        try:
            report = await pipeline.run(summary_path, pdf_path)
            eval_json.write_text(report.model_dump_json(indent=2))
            log(
                f"    {method_name}: coverage={report.evidence_coverage:.3f} "
                f"hallucination={report.hallucination_rate:.3f} "
                f"claims={report.total_claims}"
            )
            out[method_name] = eval_json
        except Exception as e:
            log(f"    {method_name} FAILED: {type(e).__name__}: {e}")
            # Save an error stub so we don't retry forever; subsequent runs
            # will see size > 500 and skip. To force-retry, delete the file.
            err_payload = {
                "error": True,
                "type": type(e).__name__,
                "message": str(e),
                "method": method_name,
                "arxiv_id": arxiv_id,
            }
            eval_json.write_text(json.dumps(err_payload, indent=2))
            out[method_name] = eval_json
    return out


async def process_one_paper(arxiv_id: str) -> dict[str, Path]:
    log(f"=== {arxiv_id} ===")
    pdf = download_paper(arxiv_id)

    summary_paths: dict[str, Path] = {}
    # Ours
    summary_paths["Ours"] = run_refined_summarization(pdf, arxiv_id)
    # 5 baselines
    baseline_paths = await run_baselines_for_paper(pdf, arxiv_id)
    summary_paths.update(baseline_paths)

    # Evaluate all 6 summaries
    eval_paths = await evaluate_summaries(arxiv_id, pdf, summary_paths)
    return eval_paths


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    paper_ids = sample(n, seed=seed)
    # Paper-level concurrency. Default 8 — OpenRouter paid tier handles
    # ~80 in-flight requests easily. Override via EXPERIMENT_CONCURRENCY.
    import os as _os
    concurrency = int(_os.environ.get("EXPERIMENT_CONCURRENCY", "8"))
    log(f"Sampled {n} papers (seed={seed}, concurrency={concurrency}): {paper_ids}")

    summary_index: dict[str, dict[str, Path]] = {}
    sem = asyncio.Semaphore(concurrency)
    completed = [0]

    async def _process_bounded(idx: int, arxiv_id: str):
        async with sem:
            log(f"---- Paper {idx}/{n}: {arxiv_id} (start, slot {completed[0] + 1}/{concurrency} active) ----")
            try:
                evals = await process_one_paper(arxiv_id)
                summary_index[arxiv_id] = evals
            except Exception as e:
                log(f"!!! Paper {arxiv_id} crashed: {type(e).__name__}: {e}")
            finally:
                completed[0] += 1
                log(f"---- Paper {idx}/{n}: {arxiv_id} done. Total completed: {completed[0]}/{n} ----")

    await asyncio.gather(
        *[_process_bounded(i, pid) for i, pid in enumerate(paper_ids, 1)]
    )

    # Write a manifest mapping paper_id → method → eval_json_path
    manifest = {
        pid: {m: str(p.relative_to(EVAL_ROOT)) for m, p in d.items()}
        for pid, d in summary_index.items()
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    log(f"Wrote manifest: {OUT / 'manifest.json'}")
    log("DONE")


if __name__ == "__main__":
    asyncio.run(main())
