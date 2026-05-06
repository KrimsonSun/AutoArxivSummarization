"""Compare v1 (Ours) vs v2 (Ours_v2) on the n=7 sub-experiment.

Reads:
  outputs/experiment/evals_strict/<id>/Ours.eval.json       (v1, existing)
  outputs/experiment/evals_strict/<id>/Ours_v2.eval.json    (v2, new)
  outputs/experiment/evals_deberta/<id>/Ours.eval.json
  outputs/experiment/evals_deberta/<id>/Ours_v2.eval.json

Reports paired Δ on F1, precision, recall, hallucination, with
bootstrap CI. Also includes B2 (Qwen-72B-naive) as the strong baseline
reference so we can see whether v2 closes the gap.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np

EVAL_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "experiment"


def load(eval_dir: str, paper_id: str, method: str) -> dict | None:
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
        return None  # fallback
    return d


def bootstrap_ci(diffs: list[float], iters: int = 10_000, seed: int = 42) -> tuple[float, float, float]:
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


def report_pair(label: str, mode_dir: str, papers: list[str]) -> None:
    print(f"\n=== {label}  (eval dir: {mode_dir}) ===")
    rows: list[dict] = []
    for pid in papers:
        v1 = load(mode_dir, pid, "Ours")
        v2 = load(mode_dir, pid, "Ours_v2")
        b2 = load(mode_dir, pid, "B2_qwen_naive")
        if v1 is None or v2 is None:
            print(f"  {pid}: missing v1 or v2 eval, skipping")
            continue
        rows.append({
            "paper": pid,
            "v1_p": v1["evidence_coverage"], "v1_r": v1["paper_recall"],
            "v1_f1": v1["f1"], "v1_hal": v1["hallucination_rate"],
            "v1_claims": v1["total_claims"],
            "v2_p": v2["evidence_coverage"], "v2_r": v2["paper_recall"],
            "v2_f1": v2["f1"], "v2_hal": v2["hallucination_rate"],
            "v2_claims": v2["total_claims"],
            "b2_f1": b2["f1"] if b2 else None,
        })

    if not rows:
        print("  no rows; nothing to compare")
        return

    print(f"\n  {'paper':<14} {'v1_F1':>6} {'v2_F1':>6} {'ΔF1':>6}  {'v1_R':>5} {'v2_R':>5} {'ΔR':>6}  {'v1#':>4} {'v2#':>4}  {'B2_F1':>6}")
    for r in rows:
        df1 = r["v2_f1"] - r["v1_f1"]
        dr  = r["v2_r"] - r["v1_r"]
        b2 = f"{r['b2_f1']:.3f}" if r['b2_f1'] is not None else "  -  "
        print(f"  {r['paper']:<14} {r['v1_f1']:.3f} {r['v2_f1']:.3f} {df1:+.3f}  "
              f"{r['v1_r']:.3f} {r['v2_r']:.3f} {dr:+.3f}  "
              f"{r['v1_claims']:>4} {r['v2_claims']:>4}  {b2}")

    # Aggregate
    df1_list = [r["v2_f1"] - r["v1_f1"] for r in rows]
    dr_list  = [r["v2_r"] - r["v1_r"] for r in rows]
    dh_list  = [r["v2_hal"] - r["v1_hal"] for r in rows]
    dp_list  = [r["v2_p"] - r["v1_p"] for r in rows]

    print(f"\n  Mean Δ across {len(rows)} papers (paired):")
    for label_, lst in [("ΔF1", df1_list), ("ΔRecall", dr_list),
                        ("ΔPrecision", dp_list), ("ΔHallucination", dh_list)]:
        m, lo, hi = bootstrap_ci(lst)
        d = cohens_d(lst)
        sig = "**" if (lo > 0 or hi < 0) else "ns"
        print(f"    {label_:<16} = {m:+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]   d = {d:+.2f}   {sig}")

    # Win/loss/tie on F1
    tol = 0.02
    wins = sum(1 for d in df1_list if d > tol)
    losses = sum(1 for d in df1_list if d < -tol)
    ties = len(df1_list) - wins - losses
    print(f"  v2 vs v1 on F1: W/L/T = {wins}/{losses}/{ties}  (papers where v2 wins / loses / ties at ±{tol})")

    # vs B2 — does v2 close the gap?
    b2_diffs_v1 = [r["v1_f1"] - r["b2_f1"] for r in rows if r["b2_f1"] is not None]
    b2_diffs_v2 = [r["v2_f1"] - r["b2_f1"] for r in rows if r["b2_f1"] is not None]
    if b2_diffs_v1:
        m1, _, _ = bootstrap_ci(b2_diffs_v1)
        m2, lo2, hi2 = bootstrap_ci(b2_diffs_v2)
        print(f"  Gap vs B2:  v1 ΔF1(Ours - B2) = {m1:+.3f}    →    v2 ΔF1(Ours_v2 - B2) = {m2:+.3f}   95% CI [{lo2:+.3f}, {hi2:+.3f}]")


def main():
    from experiment.paper_pool import sample
    papers = sample(7, seed=42)
    print(f"Comparing v1 vs v2 on {len(papers)} papers: {papers}")
    report_pair("STRICT-LLM", "evals_strict", papers)
    report_pair("DeBERTa-NLI", "evals_deberta", papers)


if __name__ == "__main__":
    main()
