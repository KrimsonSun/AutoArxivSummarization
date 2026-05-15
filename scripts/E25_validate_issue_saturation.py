#!/usr/bin/env python3
"""E25 — Validate L4: recompute mean issues raised / addressed in v1 n=29.

Source: RefinedSummarization/paper/stats.json -> issue_count_proxy.per_paper
"""
import json, statistics, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATS = ROOT / "RefinedSummarization" / "paper" / "stats.json"

def main():
    s = json.loads(STATS.read_text())
    rows = s["issue_count_proxy"]["per_paper"]
    raised = [r["issues_raised"] for r in rows]
    addressed = [r["issues_addressed_count"] for r in rows]
    evidence = [r["evidence_paragraphs_used"] for r in rows]

    n = len(rows)
    print(f"E25 — Verifier saturation audit, n={n} papers (v1 RefinedSummarization)")
    print(f"  source: {STATS.relative_to(ROOT)}")
    print()
    print("Issues raised:")
    print(f"  mean   = {statistics.mean(raised):.2f}")
    print(f"  median = {statistics.median(raised):.1f}")
    print(f"  min    = {min(raised)}, max = {max(raised)}")
    print(f"  saturated at cap (==12): {sum(1 for v in raised if v == 12)}/{n}")
    print()
    print("Issues addressed:")
    print(f"  mean   = {statistics.mean(addressed):.2f}")
    print(f"  median = {statistics.median(addressed):.1f}")
    print(f"  min    = {min(addressed)}, max = {max(addressed)}")
    print(f"  addressed-equals-raised: {sum(1 for r,a in zip(raised,addressed) if r==a)}/{n}")
    print()
    print("Evidence paragraphs used per paper:")
    print(f"  mean   = {statistics.mean(evidence):.2f}")
    print(f"  median = {statistics.median(evidence):.1f}")
    print(f"  min    = {min(evidence)}, max = {max(evidence)}")
    print()
    # L4 verdict
    sat = sum(1 for v in raised if v == 12) / n
    rubber = sum(1 for r,a in zip(raised,addressed) if r==a) / n
    print(f"L4 verdict:")
    print(f"  L4 symptom claim 'mean issues raised = 12 cap': {'CONFIRMED' if statistics.mean(raised) >= 11.5 else 'DISCONFIRMED'} (mean={statistics.mean(raised):.2f}, {sat*100:.0f}% saturated)")
    print(f"  L4 symptom claim 'mean addressed = 12, refiner rubber-stamps': {'CONFIRMED' if rubber >= 0.9 else 'DISCONFIRMED'} ({rubber*100:.0f}% raised==addressed)")

if __name__ == "__main__":
    main()
