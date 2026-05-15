#!/usr/bin/env python3
"""E27 — Decompose L9: Δ(B2 - B6) on n=29 (the pure backbone-swap contrast).

Goal: Δ(OneVision − B6) − Δ(B2 − B6) = isolated augmenter effect.
L9 hypothesis: Δ(B2 − B6) ≈ +0.16 strict / +0.17 deberta.

Required input: per-paper B2 and B6 strict/deberta vectors on n=29.
These live in the gitignored Evaluation/outputs/experiment/onevision_summary.json
which is NOT in the repo. We fall back to means-from-RESULTS_TABLE and report
unpaired decomposition; we cannot compute a paired bootstrap CI.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "Evaluation" / "outputs" / "experiment" / "onevision_summary.json"
RESULTS_TABLE = ROOT / "Refine-OneVision-Summary" / "paper" / "RESULTS_TABLE.md"

# Means as cited in RESULTS_TABLE.md (committed to repo, sourced from
# the gitignored summary at run time).
MEANS = {
    "strict": {
        "Ours_onevision": (0.584, 26),
        "B1_llama_naive": (0.503, 24),
        "B2_qwen_naive": (0.645, 24),
        "B3_deepseek_naive": (0.619, 24),
        "B4_llama8b_naive": (0.457, 26),
        "B5_llama_structured": (0.431, 26),
        "B6_llama_v2_prompt": (0.478, 25),
    },
    "deberta": {
        "Ours_onevision": (0.515, 27),
        "B1_llama_naive": (0.431, 23),
        "B2_qwen_naive": (0.559, 26),
        "B3_deepseek_naive": (0.506, 27),
        "B4_llama8b_naive": (0.407, 25),
        "B5_llama_structured": (0.383, 26),
        "B6_llama_v2_prompt": (0.389, 26),
    },
}
# Paired contrasts as published (from RESULTS_TABLE / paper):
ONEVISION_VS_B6 = {"strict": +0.106, "deberta": +0.126}  # [+0.047,+0.175] / [+0.072,+0.187]

def main():
    print("E27 — Backbone-swap decomposition Δ(B2 − B6)")
    print(f"  paired-source: {SUMMARY.relative_to(ROOT)} (gitignored — not in repo)")
    print(f"  fallback-source: {RESULTS_TABLE.relative_to(ROOT)} (means + n per cell)")
    print()
    if SUMMARY.exists():
        print("(found onevision_summary.json — could compute paired CI; not implemented in this fallback path)")
        print()
    for judge in ("strict", "deberta"):
        m = MEANS[judge]
        b2_mean, b2_n = m["B2_qwen_naive"]
        b6_mean, b6_n = m["B6_llama_v2_prompt"]
        delta_b2_b6 = b2_mean - b6_mean
        ov_b6 = ONEVISION_VS_B6[judge]
        augmenter = ov_b6 - delta_b2_b6
        print(f"[{judge}-LLM judge]")
        print(f"  B2 Qwen     mean F1 = {b2_mean:.3f}  (n={b2_n})")
        print(f"  B6 Llama-v2 mean F1 = {b6_mean:.3f}  (n={b6_n})")
        print(f"  Δ(B2 − B6) unpaired = {delta_b2_b6:+.3f}   [L9 hypothesis: ~{'+0.16' if judge=='strict' else '+0.17'}]")
        print(f"  Δ(OneVision − B6)    = {ov_b6:+.3f}        [paired, published]")
        print(f"  augmenter component  = Δ(OV − B6) − Δ(B2 − B6) = {augmenter:+.3f}")
        # interpretation
        backbone = delta_b2_b6
        net = ov_b6
        if backbone > 0 and augmenter < 0:
            print(f"  -> Decomposition: backbone swap (Llama→Qwen) contributes {backbone:+.3f},")
            print(f"     augmenter degrades by {augmenter:+.3f}. Net OneVision over B6 = {net:+.3f}.")
        print()
    print("Hypothesis check (L9):")
    delta_strict = MEANS["strict"]["B2_qwen_naive"][0] - MEANS["strict"]["B6_llama_v2_prompt"][0]
    delta_deb = MEANS["deberta"]["B2_qwen_naive"][0] - MEANS["deberta"]["B6_llama_v2_prompt"][0]
    print(f"  L9 expected Δ(B2−B6) ≈ +0.16 strict / +0.17 deberta")
    print(f"  observed (unpaired): {delta_strict:+.3f} strict, {delta_deb:+.3f} deberta")
    near = abs(delta_strict - 0.16) < 0.03 and abs(delta_deb - 0.17) < 0.03
    print(f"  -> L9 numerical claim {'CONFIRMED (within 0.03)' if near else 'NEEDS REVISION'}")
    print()
    print("CAVEAT: paired CI not computable without onevision_summary.json. ")
    print("Per-paper B6 vectors live in Evaluation/outputs/experiment/onevision_summary.json")
    print("(gitignored). Promote that file to a committed artifact (or write a per-paper")
    print("export hook in compare_onevision.py) to enable a paired bootstrap re-run.")

if __name__ == "__main__":
    main()
