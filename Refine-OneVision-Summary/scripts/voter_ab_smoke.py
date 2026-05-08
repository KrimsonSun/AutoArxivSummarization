"""Voter A/B smoke test — n=3 papers, claim_grounding vs borda.

For each paper, runs the full OneVision pipeline twice (once per voting
method) and writes a side-by-side report:

  - voter winner per paper
  - per-draft scoring (issues, words, density for claim_grounding;
    Borda totals + per-axis means for borda)
  - token usage / cost estimate

Authentication: requires OPENAI_API_KEY (an OpenRouter key, sk-or-v1-...)
and OPENAI_BASE_URL=https://openrouter.ai/api/v1 in the environment, OR
in the project root .env. Exits 1 with a clear message if missing.

Usage (from Refine-OneVision-Summary/):
    OPENAI_API_KEY=sk-or-v1-... \
    OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
    python scripts/voter_ab_smoke.py [--n 3] [--out reports/]
"""
from __future__ import annotations

import argparse
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

from src.config.loader import load_config
from src.pipeline import OneVisionPipeline


PAPER_POOL = [
    "1706.03762",  # Attention
    "2004.04906",  # DPR — known DPR case-study paper from L5
    "2005.11401",  # RAG
    "2106.09685",  # LoRA
    "2305.18290",  # DPO
    "2210.03629",  # ReAct
    "2305.10601",  # Tree of Thoughts
    "2308.08155",  # AutoGen
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def download_paper(arxiv_id: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = dest_dir / f"{arxiv_id}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 50_000:
        return pdf_path
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    log(f"  downloading {arxiv_id} from {url}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "AutoArxivSummarization/voter-ab-smoke"}
    )
    with urllib.request.urlopen(req, timeout=60) as r, open(pdf_path, "wb") as f:
        f.write(r.read())
    return pdf_path


async def run_one(pdf: Path, config_path: str) -> dict:
    cfg = load_config(config_path)
    pipeline = OneVisionPipeline(cfg)
    t0 = time.monotonic()
    final, transcript = await pipeline.run(pdf)
    elapsed = time.monotonic() - t0
    return {
        "method": cfg.pipeline.voting.method,
        "winner_agent_id": transcript.winner_agent_id,
        "winner_label": transcript.winner_label,
        "per_label_borda": dict(transcript.per_label_borda),
        "label_to_agent": dict(transcript.label_to_agent),
        "claim_grounding_scores": [
            s.model_dump() for s in (transcript.claim_grounding_scores or [])
        ],
        "tokens_prompt": final.metadata.total_tokens_used.get("prompt", 0),
        "tokens_completion": final.metadata.total_tokens_used.get("completion", 0),
        "total_calls": final.metadata.total_llm_calls,
        "n_issues_raised": final.metadata.issues_raised,
        "n_issues_addressed": len(final.metadata.issues_addressed),
        "wall_seconds": round(elapsed, 1),
    }


async def run_paper(arxiv_id: str, pdf: Path, configs: list[tuple[str, str]]) -> dict:
    """Run all configs on one paper sequentially (rate-limit safe)."""
    out: dict = {"arxiv_id": arxiv_id, "results": {}}
    for method_label, cfg_path in configs:
        log(f"  → {arxiv_id} via {method_label} ({cfg_path})")
        try:
            res = await run_one(pdf, cfg_path)
        except Exception as e:
            log(f"    !! {method_label} failed: {type(e).__name__}: {str(e)[:200]}")
            res = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
        out["results"][method_label] = res
    return out


def render_report(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Voter A/B smoke report")
    lines.append("")
    lines.append(f"- n_papers: {len(report['papers'])}")
    lines.append(f"- timestamp: {report['timestamp']}")
    lines.append("")

    # Aggregate winners.
    cg_wins: dict[str, int] = {}
    bd_wins: dict[str, int] = {}
    for p in report["papers"]:
        cg = p["results"].get("claim_grounding", {})
        bd = p["results"].get("borda", {})
        if cg.get("winner_agent_id"):
            cg_wins[cg["winner_agent_id"]] = cg_wins.get(cg["winner_agent_id"], 0) + 1
        if bd.get("winner_agent_id"):
            bd_wins[bd["winner_agent_id"]] = bd_wins.get(bd["winner_agent_id"], 0) + 1
    lines.append("## Winner aggregate")
    lines.append("")
    lines.append("| method | agent_qwen | agent_llama | agent_deepseek |")
    lines.append("|---|---:|---:|---:|")
    for label, d in (("claim_grounding", cg_wins), ("borda", bd_wins)):
        q = d.get("agent_qwen", 0)
        l = d.get("agent_llama", 0)
        ds = d.get("agent_deepseek", 0)
        lines.append(f"| {label} | {q} | {l} | {ds} |")
    lines.append("")

    # Per-paper detail.
    for p in report["papers"]:
        lines.append(f"## {p['arxiv_id']}")
        lines.append("")
        for method_label in ("claim_grounding", "borda"):
            res = p["results"].get(method_label, {})
            lines.append(f"### {method_label}")
            if "error" in res:
                lines.append(f"  ERROR: {res['error']}")
                lines.append("")
                continue
            lines.append(f"  - winner: **{res['winner_agent_id']}** (label {res['winner_label']})")
            lines.append(f"  - tokens: prompt={res['tokens_prompt']}, completion={res['tokens_completion']}, calls={res['total_calls']}")
            lines.append(f"  - wall: {res['wall_seconds']:.1f}s")
            lines.append(f"  - issues raised/addressed: {res['n_issues_raised']}/{res['n_issues_addressed']}")
            if res.get("claim_grounding_scores"):
                lines.append("  - per-draft scoring:")
                for s in res["claim_grounding_scores"]:
                    lines.append(
                        f"    {s['draft_label']} ({s['agent_id']}): "
                        f"words={s['word_count']}, total={s['n_total_issues']}, "
                        f"missing={s['n_missing_info']}, "
                        f"density={s['issues_per_100_words']:.3f}"
                    )
            lines.append(f"  - per_label_borda: {res['per_label_borda']}")
            lines.append("")
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3, help="Number of papers")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="reports/voter_ab_smoke")
    args = parser.parse_args()

    # Validate environment via the project's centralised settings loader
    # so the .env file (repo-root or project-local) is consulted, not just
    # the raw shell environment.
    from src.config.settings import settings  # noqa: E402
    api_key = settings.OPENAI_API_KEY.get_secret_value().strip()
    base = (settings.OPENAI_BASE_URL or "").strip()
    if not api_key:
        log("ERROR: OPENAI_API_KEY is unset. Set OPENROUTER key (sk-or-v1-...) "
            "in repo-root .env or via the shell.")
        return 1
    if not base:
        log("WARN: OPENAI_BASE_URL is unset; defaulting to OpenAI endpoint. "
            "Set OPENAI_BASE_URL=https://openrouter.ai/api/v1 if you intended OpenRouter.")

    rng = random.Random(args.seed)
    arxiv_ids = rng.sample(PAPER_POOL, args.n)
    log(f"sampled {args.n} papers (seed={args.seed}): {arxiv_ids}")

    pdf_dir = ROOT / "outputs" / "smoke_pdfs"
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        ("claim_grounding", "config/default.yaml"),
        ("borda", "config/borda_legacy.yaml"),
    ]

    papers: list[dict] = []
    for arxiv_id in arxiv_ids:
        log(f"=== {arxiv_id} ===")
        try:
            pdf = download_paper(arxiv_id, pdf_dir)
        except Exception as e:
            log(f"  download failed: {type(e).__name__}: {e}")
            papers.append({"arxiv_id": arxiv_id, "error": str(e), "results": {}})
            continue
        out = await run_paper(arxiv_id, pdf, configs)
        papers.append(out)
        # Persist incrementally.
        (out_dir / f"{arxiv_id}.json").write_text(json.dumps(out, indent=2))

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_papers": args.n,
        "papers": papers,
    }
    (out_dir / "smoke_report.json").write_text(json.dumps(report, indent=2))
    md = render_report(report)
    (out_dir / "smoke_report.md").write_text(md)
    log(f"wrote {out_dir/'smoke_report.md'}")
    print()
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
