"""Run OneVision (claim_grounding voter, Fix 3) on n=29 papers.

Writes:
  Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3.json
  Evaluation/outputs/experiment/summaries/<id>/Ours_onevision_v3.voting.json
  Refine-OneVision-Summary/reports/n29_run/summary.md
        — aggregate winner distribution + per-paper outcome.

Does NOT run baselines or evaluation. Baselines for n=29 already exist
in RefinedSummarization/paper/stats.json; evaluation is a separate
strict_reeval invocation against the written JSONs.

Concurrency = 3 by default (override with EXPERIMENT_CONCURRENCY env).

Usage:
    cd Refine-OneVision-Summary
    EXPERIMENT_CONCURRENCY=3 python scripts/run_onevision_n29.py
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EVAL_OUT = ROOT.parent / "Evaluation" / "outputs" / "experiment"
SUMS = EVAL_OUT / "summaries"
PAPERS = EVAL_OUT / "papers"
REPORT_DIR = ROOT / "reports" / "n29_run"
SUMS.mkdir(parents=True, exist_ok=True)
PAPERS.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# Same paper pool as Evaluation/experiment/paper_pool.py.
PAPER_POOL = [
    "1706.03762", "1810.04805", "2005.14165", "2104.08691", "2106.09685",
    "2310.06825", "2402.17764", "2305.10403", "2204.02311", "2203.15556",
    "2001.08361", "2203.02155", "2305.18290", "2204.05862", "2201.11903",
    "2210.03629", "2305.10601", "2308.08155", "2010.11929", "2103.00020",
    "2204.06125", "2304.02643", "2006.11239", "2112.10752", "1707.06347",
    "2305.14233", "2005.11401", "2004.04906", "2106.04561", "2205.14135",
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def download_paper(arxiv_id: str) -> Path:
    pdf = PAPERS / f"{arxiv_id}.pdf"
    if pdf.exists() and pdf.stat().st_size > 50_000:
        return pdf
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    log(f"  downloading {arxiv_id}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "AutoArxivSummarization/n29-run"}
    )
    with urllib.request.urlopen(req, timeout=120) as r, open(pdf, "wb") as f:
        f.write(r.read())
    return pdf


async def run_one(
    arxiv_id: str,
    method_name: str = "Ours_onevision_v3",
    config_path: str = "config/default.yaml",
) -> dict:
    """Run OneVision pipeline on one paper. Returns summary record."""
    sum_dir = SUMS / arxiv_id
    sum_dir.mkdir(parents=True, exist_ok=True)
    out_json = sum_dir / f"{method_name}.json"
    voting_json = sum_dir / f"{method_name}.voting.json"

    if out_json.exists() and out_json.stat().st_size > 1000:
        log(f"  {arxiv_id}: cached")
        cached = json.loads(out_json.read_text())
        cached_voting = json.loads(voting_json.read_text()) if voting_json.exists() else {}
        return {
            "arxiv_id": arxiv_id,
            "winner_agent_id": cached_voting.get("winner_agent_id"),
            "claim_grounding_scores": cached_voting.get("claim_grounding_scores"),
            "tokens_prompt": cached.get("metadata", {}).get("total_tokens_used", {}).get("prompt"),
            "tokens_completion": cached.get("metadata", {}).get("total_tokens_used", {}).get("completion"),
            "n_issues": cached.get("metadata", {}).get("issues_raised"),
            "cached": True,
        }

    pdf = download_paper(arxiv_id)
    # Lazy import (some heavy deps).
    from src.config.loader import load_config
    from src.pipeline import OneVisionPipeline

    cfg = load_config(config_path)
    pipeline = OneVisionPipeline(cfg)
    t0 = time.monotonic()
    final, transcript = await pipeline.run(pdf)
    elapsed = time.monotonic() - t0

    out_json.write_text(final.model_dump_json(indent=2))
    voting_json.write_text(transcript.model_dump_json(indent=2))
    log(f"  {arxiv_id}: winner={transcript.winner_agent_id} t={elapsed:.0f}s")

    return {
        "arxiv_id": arxiv_id,
        "winner_agent_id": transcript.winner_agent_id,
        "winner_label": transcript.winner_label,
        "claim_grounding_scores": [
            s.model_dump() for s in (transcript.claim_grounding_scores or [])
        ],
        "tokens_prompt": final.metadata.total_tokens_used.get("prompt", 0),
        "tokens_completion": final.metadata.total_tokens_used.get("completion", 0),
        "n_issues": final.metadata.issues_raised,
        "wall_seconds": elapsed,
        "cached": False,
    }


async def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/default.yaml",
                        help="OneVision config path (relative to Refine-OneVision-Summary/).")
    parser.add_argument("--method-name", default="Ours_onevision_v3",
                        help="Output filename stem under summaries/<id>/.")
    parser.add_argument("--report-dir", default="reports/n29_run",
                        help="Where to write summary.{md,json}.")
    args = parser.parse_args()

    # Validate env via centralised settings (same path as the pipeline uses).
    from src.config.settings import settings
    if not settings.OPENAI_API_KEY.get_secret_value().strip():
        log("ERROR: OPENAI_API_KEY unset.")
        return 1

    arxiv_ids = list(PAPER_POOL)  # 30 in the pool.
    log(f"running OneVision (config={args.config}, method={args.method_name}) on {len(arxiv_ids)} papers")

    concurrency = int(os.environ.get("EXPERIMENT_CONCURRENCY", "3"))
    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def _gated(pid: str) -> None:
        async with sem:
            try:
                r = await run_one(pid, method_name=args.method_name, config_path=args.config)
                results.append(r)
            except Exception as e:
                log(f"  {pid}: FAILED — {type(e).__name__}: {str(e)[:200]}")
                results.append({"arxiv_id": pid, "error": f"{type(e).__name__}: {str(e)[:300]}"})

    t0 = time.monotonic()
    await asyncio.gather(*[_gated(pid) for pid in arxiv_ids])
    elapsed = time.monotonic() - t0
    log(f"all {len(arxiv_ids)} papers attempted, {elapsed/60:.1f} minutes wall")

    # Aggregate.
    winners: dict[str, int] = {}
    total_prompt = total_completion = 0
    successes = 0
    failures: list[str] = []
    rows: list[dict] = sorted(results, key=lambda r: r["arxiv_id"])
    for r in rows:
        if "error" in r:
            failures.append(r["arxiv_id"])
            continue
        successes += 1
        if r.get("winner_agent_id"):
            winners[r["winner_agent_id"]] = winners.get(r["winner_agent_id"], 0) + 1
        total_prompt += r.get("tokens_prompt") or 0
        total_completion += r.get("tokens_completion") or 0

    REPORT_OUT = ROOT / args.report_dir
    REPORT_OUT.mkdir(parents=True, exist_ok=True)
    # Write JSON + Markdown report.
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "method": "claim_grounding (Fix 1+2+3)",
        "n_attempted": len(arxiv_ids),
        "n_successes": successes,
        "n_failures": len(failures),
        "wall_seconds": round(elapsed, 1),
        "tokens_prompt_total": total_prompt,
        "tokens_completion_total": total_completion,
        "winner_distribution": winners,
        "papers": rows,
    }
    (REPORT_OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    md = [f"# OneVision n=29 — config={args.config}, method={args.method_name}"]
    md.append("")
    md.append(f"- timestamp: {summary['timestamp']}")
    md.append(f"- attempted: {summary['n_attempted']}, successes: {successes}, failures: {len(failures)}")
    md.append(f"- wall: {elapsed/60:.1f} min")
    md.append(f"- tokens: prompt={total_prompt}, completion={total_completion}")
    md.append("")
    md.append("## Winner distribution")
    md.append("")
    n_evaluable = max(successes, 1)
    for agent in ("agent_qwen", "agent_llama", "agent_deepseek"):
        c = winners.get(agent, 0)
        md.append(f"- {agent}: **{c} / {n_evaluable}** ({100 * c / n_evaluable:.1f} %)")
    md.append("")
    md.append("## Comparison to PER_PAPER_AUDIT (Borda voter, n=28)")
    md.append("")
    md.append("| Voter | Qwen | Llama | DeepSeek |")
    md.append("|---|---|---|---|")
    md.append("| Borda (legacy, original n=29 audit) | **26 / 28 (92.9 %)** | 2 / 28 (7.1 %) | 0 / 28 |")
    q = winners.get("agent_qwen", 0)
    l = winners.get("agent_llama", 0)
    d = winners.get("agent_deepseek", 0)
    md.append(f"| **claim_grounding (Fix 3)** | {q} / {successes} | {l} / {successes} | {d} / {successes} |")
    md.append("")
    if failures:
        md.append(f"## Failures: {len(failures)}")
        md.append("")
        for fid in failures:
            md.append(f"- {fid}")
        md.append("")
    md.append("## Per-paper detail")
    md.append("")
    md.append("| arxiv_id | winner | Qwen mi | Llama mi | DS mi |")
    md.append("|---|---|---:|---:|---:|")
    for r in rows:
        if "error" in r:
            md.append(f"| {r['arxiv_id']} | ERROR | - | - | - |")
            continue
        winner = r.get("winner_agent_id", "?")
        scores_by_agent: dict[str, int] = {}
        for s in r.get("claim_grounding_scores") or []:
            scores_by_agent[s["agent_id"]] = s.get("n_missing_info", -1)
        md.append(
            f"| {r['arxiv_id']} | {winner} | "
            f"{scores_by_agent.get('agent_qwen','-')} | "
            f"{scores_by_agent.get('agent_llama','-')} | "
            f"{scores_by_agent.get('agent_deepseek','-')} |"
        )

    (REPORT_OUT / "summary.md").write_text("\n".join(md))
    log(f"wrote {REPORT_OUT/'summary.md'}")
    log(f"  successes: {successes}, failures: {len(failures)}")
    log(f"  winner_distribution: {winners}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
