#!/usr/bin/env python3
"""E28 — Re-fill missing CI for B5 vs B1 paired bootstrap on n=29.

Source: stats.json paired_diffs_Ours_vs.{Ours_vs_B1, Ours_vs_B5}.per_paper
Each entry has bl_strict / bl_deberta = the baseline's score on that paper.
We pair B5 and B1 by paper id, compute paired diff, bootstrap 95 % CI.
Linked: L6 (M4 retraction).
"""
import json, pathlib, random, statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATS = ROOT / "RefinedSummarization" / "paper" / "stats.json"

def bootstrap_ci(diffs, n_resamples=10000, seed=42):
    rng = random.Random(seed)
    means = []
    n = len(diffs)
    for _ in range(n_resamples):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample)/n)
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples)]
    return lo, hi

def cohens_d(diffs):
    if len(diffs) < 2: return 0.0
    sd = statistics.stdev(diffs)
    return (statistics.mean(diffs) / sd) if sd > 0 else 0.0

def main():
    s = json.loads(STATS.read_text())
    b1_pp = s["paired_diffs_Ours_vs"]["Ours_vs_B1_llama_naive"]["per_paper"]
    b5_pp = s["paired_diffs_Ours_vs"]["Ours_vs_B5_llama_structured"]["per_paper"]
    b1_by = {r["paper"]: r for r in b1_pp}
    b5_by = {r["paper"]: r for r in b5_pp}
    common = sorted(set(b1_by) & set(b5_by))
    print(f"E28 — B5 vs B1 paired bootstrap, n_common = {len(common)}")
    print(f"  source: {STATS.relative_to(ROOT)}")
    print()
    for judge_key, label in (("bl_strict", "strict-LLM"), ("bl_deberta", "DeBERTa-NLI")):
        diffs = []
        b5_vec = []
        b1_vec = []
        wins = ties = losses = 0
        for pid in common:
            v5 = b5_by[pid].get(judge_key)
            v1 = b1_by[pid].get(judge_key)
            if v5 is None or v1 is None:
                continue
            d = v5 - v1
            diffs.append(d)
            b5_vec.append(v5)
            b1_vec.append(v1)
            if d > 0.001: wins += 1
            elif d < -0.001: losses += 1
            else: ties += 1
        n = len(diffs)
        m = statistics.mean(diffs)
        lo, hi = bootstrap_ci(diffs)
        d_eff = cohens_d(diffs)
        sig = "ns" if (lo <= 0 <= hi) else "★★"
        print(f"[{label} judge]  n_paired = {n}")
        print(f"  mean B5 = {statistics.mean(b5_vec):.3f},  mean B1 = {statistics.mean(b1_vec):.3f}")
        print(f"  ΔF1(B5 − B1) = {m:+.4f}   95 % CI [{lo:+.4f}, {hi:+.4f}]   d = {d_eff:+.3f}   {sig}")
        print(f"  W/L/T (B5 over B1) = {wins}/{losses}/{ties}")
        print()
    print("L6 verdict (M4 retraction):")
    print("  M4 'schema rewards abstraction' was retracted because B5−B1 was −0.04 (ns) in unpaired means.")
    print("  Paired bootstrap above quantifies whether that null is a confidently null result, or just")
    print("  underpowered. CI excluding 0 in either direction would mean L6 needs softening.")

if __name__ == "__main__":
    main()
