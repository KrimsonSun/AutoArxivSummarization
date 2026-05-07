"""OneVision vs baselines comparison (n=15).

Reads:
  outputs/experiment/evals_strict/<id>/{Ours_onevision,B1..B6}.eval.json
  outputs/experiment/evals_deberta/<id>/{Ours_onevision,B1..B6}.eval.json
  outputs/experiment/summaries/<id>/{Ours_onevision.json, B1..B6.md}  (length info)

Reports per evaluator:
  - Mean F1 / F0.5 / F2 / P / R / hallucination per method
  - Paired bootstrap CI on (Ours_onevision − baseline) for B1, B2, B6
  - Mean summary length (words) per method
  - Per-paper table (paper, method, F1)

Writes outputs/experiment/onevision_summary.json with all the numbers
the figure renderer (plot_onevision.py) and the paper need.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np

EVAL_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "experiment"

METHODS = [
    "Ours_onevision",
    "B1_llama_naive",
    "B2_qwen_naive",
    "B3_deepseek_naive",
    "B4_llama8b_naive",
    "B5_llama_structured",
    "B6_llama_v2prompt",
]


def load_eval(eval_dir: str, paper_id: str, method: str) -> dict | None:
    p = EVAL_ROOT / eval_dir / paper_id / f"{method}.eval.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except Exception:
        return None
    if d.get("error"):
        return None
    if d.get("paper_recall", -1) == 0.0 and d.get("evidence_coverage", 0) > 0:
        return None  # recall-checker fallback
    return d


def boot_ci(diffs: list[float], iters: int = 10_000, seed: int = 42) -> tuple[float, float, float]:
    arr = np.array(diffs)
    rng = np.random.default_rng(seed)
    boot = np.array([
        arr[rng.integers(0, len(arr), size=len(arr))].mean()
        for _ in range(iters)
    ])
    return float(arr.mean()), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def cohens_d(diffs: list[float]) -> float:
    if len(diffs) < 2:
        return 0.0
    mu = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    return mu / sd if sd > 0 else 0.0


def mean_or_none(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    return statistics.mean(valid) if valid else None


def measure_length(paper_id: str, method: str) -> int | None:
    """Return word count of summary file (md or json)."""
    sum_dir = EVAL_ROOT / "summaries" / paper_id
    md = sum_dir / f"{method}.md"
    js = sum_dir / f"{method}.json"
    if md.exists():
        return len(md.read_text().split())
    if js.exists():
        try:
            d = json.loads(js.read_text())
        except Exception:
            return None
        if d.get("error"):
            return None
        text_pieces: list[str] = []
        for k in ("tldr", "core_idea"):
            v = d.get(k)
            if isinstance(v, str):
                text_pieces.append(v)
        for c in d.get("key_contributions") or []:
            text_pieces.append(c.get("text", "") if isinstance(c, dict) else str(c))
        m = d.get("method") or {}
        text_pieces.append(m.get("overview", ""))
        for comp in m.get("components") or []:
            text_pieces.append(comp.get("name", "") + " " + comp.get("description", ""))
        e = d.get("experiments") or {}
        text_pieces.append(e.get("setup", ""))
        for f in e.get("key_findings") or []:
            text_pieces.append(f.get("text", "") if isinstance(f, dict) else str(f))
        for lim in d.get("limitations") or []:
            text_pieces.append(lim if isinstance(lim, str) else "")
        return sum(len(t.split()) for t in text_pieces)
    return None


def report_mode(label: str, eval_dir: str, papers: list[str]) -> dict:
    print(f"\n=== {label}  (eval_dir={eval_dir}) ===")
    rows: list[dict] = []
    for pid in papers:
        cells = {m: load_eval(eval_dir, pid, m) for m in METHODS}
        if cells["Ours_onevision"] is None:
            print(f"  {pid}: missing Ours_onevision eval, skipping")
            continue
        row = {"paper": pid, "cells": cells}
        rows.append(row)

    if not rows:
        print("  no rows")
        return {}

    # Per-method summary stats.
    print(f"\n  {'method':<25} {'n':>3} {'mean F1':>8} {'F0.5':>7} {'F2':>7} "
          f"{'P':>7} {'R':>7} {'hal':>7} {'words':>7}")
    method_stats: dict[str, dict] = {}
    for m in METHODS:
        f1s = [r["cells"][m]["f1"] for r in rows if r["cells"][m] is not None]
        fhs = [r["cells"][m].get("f_half", 0.0) for r in rows if r["cells"][m] is not None]
        fts = [r["cells"][m].get("f_two", 0.0) for r in rows if r["cells"][m] is not None]
        ps  = [r["cells"][m]["evidence_coverage"] for r in rows if r["cells"][m] is not None]
        rs  = [r["cells"][m]["paper_recall"] for r in rows if r["cells"][m] is not None]
        hs  = [r["cells"][m]["hallucination_rate"] for r in rows if r["cells"][m] is not None]
        words = [measure_length(r["paper"], m) for r in rows]
        word_mean = mean_or_none([w for w in words if w is not None])
        if not f1s:
            print(f"  {m:<25} {0:>3}     n/a")
            continue
        print(f"  {m:<25} {len(f1s):>3} "
              f"{statistics.mean(f1s):>8.3f} "
              f"{statistics.mean(fhs):>7.3f} "
              f"{statistics.mean(fts):>7.3f} "
              f"{statistics.mean(ps):>7.3f} "
              f"{statistics.mean(rs):>7.3f} "
              f"{statistics.mean(hs):>7.3f} "
              f"{(word_mean or 0):>7.0f}")
        method_stats[m] = {
            "n": len(f1s),
            "mean_f1": statistics.mean(f1s),
            "mean_f_half": statistics.mean(fhs),
            "mean_f_two": statistics.mean(fts),
            "mean_p": statistics.mean(ps),
            "mean_r": statistics.mean(rs),
            "mean_hal": statistics.mean(hs),
            "mean_words": word_mean,
        }

    # Paired contrasts: Ours_onevision − each baseline (where both are present).
    print("\n  Paired (Ours_onevision − baseline), n papers where BOTH have valid evals:")
    contrasts: dict[str, dict] = {}
    for m in METHODS[1:]:  # skip Ours_onevision itself
        diffs_f1 = []
        diffs_fh = []
        diffs_r  = []
        for r in rows:
            ov = r["cells"]["Ours_onevision"]
            bl = r["cells"][m]
            if ov is None or bl is None:
                continue
            diffs_f1.append(ov["f1"] - bl["f1"])
            diffs_fh.append(ov.get("f_half", 0.0) - bl.get("f_half", 0.0))
            diffs_r.append(ov["paper_recall"] - bl["paper_recall"])
        if not diffs_f1:
            continue
        m_f1, lo_f1, hi_f1 = boot_ci(diffs_f1)
        m_fh, lo_fh, hi_fh = boot_ci(diffs_fh)
        m_r,  lo_r,  hi_r  = boot_ci(diffs_r)
        sig = "**" if (lo_f1 > 0 or hi_f1 < 0) else "ns"
        print(f"  {m:<25}  ΔF1={m_f1:+.3f} CI[{lo_f1:+.3f}, {hi_f1:+.3f}] {sig}  "
              f"ΔF0.5={m_fh:+.3f}  ΔR={m_r:+.3f}")
        contrasts[m] = {
            "n_paired": len(diffs_f1),
            "delta_f1": {"mean": m_f1, "ci_low": lo_f1, "ci_high": hi_f1, "d": cohens_d(diffs_f1)},
            "delta_f_half": {"mean": m_fh, "ci_low": lo_fh, "ci_high": hi_fh, "d": cohens_d(diffs_fh)},
            "delta_r": {"mean": m_r, "ci_low": lo_r, "ci_high": hi_r, "d": cohens_d(diffs_r)},
        }

    return {
        "mode": label,
        "n_papers": len(rows),
        "papers_used": [r["paper"] for r in rows],
        "method_stats": method_stats,
        "contrasts_vs_ours_onevision": contrasts,
    }


def main() -> None:
    from experiment.paper_pool import sample
    papers = sample(15, seed=42)
    print(f"comparing OneVision on {len(papers)} papers: {papers}")
    out_strict  = report_mode("STRICT-LLM",   "evals_strict",  papers)
    out_deberta = report_mode("DeBERTa-NLI",  "evals_deberta", papers)

    persist = {"strict": out_strict, "deberta": out_deberta}
    out_path = EVAL_ROOT / "onevision_summary.json"
    out_path.write_text(json.dumps(persist, indent=2, default=lambda o: None))
    print(f"\nWrote summary -> {out_path}")


if __name__ == "__main__":
    main()
