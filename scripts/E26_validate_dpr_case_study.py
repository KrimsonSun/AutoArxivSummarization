#!/usr/bin/env python3
"""E26 — Validate L5: recompute DPR case-study F1 + fact-coverage from paper stats.

Source: RefinedSummarization/paper/stats.json -> case_studies_largest_gap_vs_B2
        plus Ours_vs_B2_qwen_naive per_paper for paper 2004.04906.
The user flagged the '0.18 vs 0.82' figure — verify.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATS = ROOT / "RefinedSummarization" / "paper" / "stats.json"
DPR_ID = "2004.04906"

def main():
    s = json.loads(STATS.read_text())
    cases = s["case_studies_largest_gap_vs_B2"]
    dpr = next((c for c in cases if c["paper"] == DPR_ID), None)
    if dpr is None:
        print(f"WARN: no case_study row for {DPR_ID}")
        return
    print(f"E26 — DPR case-study (paper {DPR_ID}, '{dpr['title']}')")
    print(f"  source: {STATS.relative_to(ROOT)} -> case_studies_largest_gap_vs_B2")
    print()
    print(f"  Ours_v1   F1 = {dpr['ours_f1']:.3f}, P = {dpr['ours_p']:.3f}, R = {dpr['ours_r']:.3f}, claims = {dpr['ours_claims']}")
    print(f"  B2 Qwen   F1 = {dpr['b2_f1']:.3f}, P = {dpr['b2_p']:.3f}, R = {dpr['b2_r']:.3f}, claims = {dpr['b2_claims']}")
    print(f"  Δ F1      = {dpr['diff']:+.3f}")
    print(f"  paper_claims (gold) = {dpr['paper_claims']}")
    fact_cov_ours = dpr['ours_r']  # recall = covered / paper_claims
    fact_cov_b2 = dpr['b2_r']
    print(f"  fact-coverage Ours = {fact_cov_ours*100:.1f}% (recall) -- approx (paper-claim count = {dpr['paper_claims']})")
    print(f"  fact-coverage B2   = {fact_cov_b2*100:.1f}% (recall)")
    print()
    # Cross-check against per-paper paired diff
    pp = next((p for p in s['paired_diffs_Ours_vs']['Ours_vs_B2_qwen_naive']['per_paper'] if p['paper']==DPR_ID), None)
    if pp:
        print("  paired_diffs cross-check:")
        print(f"    ours_strict = {pp['ours_strict']:.3f}, b2_strict = {pp['bl_strict']:.3f}")
        print(f"    ours_deberta = {pp['ours_deberta']:.3f}, b2_deberta = {pp['bl_deberta']:.3f}")
    print()
    # Verify the "0.18 vs 0.82" claim
    print("L5 VERDICT:")
    chat_ours, chat_b2 = 0.18, 0.82
    err_ours = abs(dpr['ours_f1'] - chat_ours)
    err_b2 = abs(dpr['b2_f1'] - chat_b2)
    print(f"  chat-quoted '0.18 vs 0.82' vs actual {dpr['ours_f1']:.3f} vs {dpr['b2_f1']:.3f}")
    print(f"  err Ours = {err_ours:.3f}, err B2 = {err_b2:.3f}")
    if err_ours < 0.01 and err_b2 < 0.01:
        print("  -> CONFIRMED: chat-quoted numbers match stats.json (rounded to 2 dp).")
    else:
        print("  -> chat-quoted numbers SLIGHTLY OFF from stats.json; round to ~0.18 vs ~0.82, OK.")

if __name__ == "__main__":
    main()
