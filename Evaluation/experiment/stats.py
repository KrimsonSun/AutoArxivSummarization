"""Statistical analysis on existing v1 evaluation data — no API calls.

Produces:
  outputs/experiment/plots/_stats.json
    {
      "n_papers": 29,
      "per_method": {
        "Ours": {"mean_f1": ..., "std_f1": ..., ...},
        "B1_llama_naive": {...},
        ...
      },
      "paired_diffs": {
        "Ours_vs_B2_qwen_naive": {
          "n": 29,
          "mean_diff": -0.20,
          "ci95_low": -0.25,
          "ci95_high": -0.15,
          "cohens_d": -1.4,
          "wins": 2,
          "losses": 25,
          "ties": 2,
          "win_rate": 0.07
        },
        ...
      },
      "issue_type_distribution": {
        "factual_error": 12,
        "missing_info": 18,
        ...
      },
      "by_paper_f1": [
        {"paper": "1706.03762", "Ours": 0.66, "B1": 0.42, ...},
        ...
      ]
    }

  outputs/experiment/plots/_per_paper_scatter.png
    A grid showing per-paper F1 for Ours vs each baseline; diagonal = tie.

  outputs/experiment/plots/_diff_distribution.png
    Histogram of F1(Ours) - F1(B2) per paper, with bootstrap CI annotation.

This script is pure pandas/numpy, no API calls; runs in seconds.
"""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

EVAL_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "experiment"
PLOTS = EVAL_ROOT / "plots"

METHOD_KEYS = [
    "Ours",
    "B1_llama_naive",
    "B2_qwen_naive",
    "B3_deepseek_naive",
    "B4_llama8b_naive",
    "B5_llama_structured",
]
METHOD_LABELS = {
    "Ours": "Ours",
    "B1_llama_naive": "B1 Llama-70B",
    "B2_qwen_naive": "B2 Qwen-72B",
    "B3_deepseek_naive": "B3 DeepSeek-V3",
    "B4_llama8b_naive": "B4 Llama-8B",
    "B5_llama_structured": "B5 Llama-struct",
}


# ---------------------------------------------------------------- loading

def load_strict_evals() -> dict[str, dict[str, dict]]:
    """Returns {paper_id: {method: report_dict}} from strict-LLM evals."""
    out: dict[str, dict[str, dict]] = {}
    for paper_dir in sorted((EVAL_ROOT / "evals_strict").iterdir()):
        if not paper_dir.is_dir():
            continue
        pid = paper_dir.name
        for ep in paper_dir.glob("*.eval.json"):
            try:
                d = json.loads(ep.read_text())
            except Exception:
                continue
            if d.get("error"):
                continue
            # Flag fallback (defensive — shouldn't happen at this stage)
            if d.get("paper_recall", -1) == 0.0 and d.get("evidence_coverage", 0) > 0:
                continue
            method = ep.stem.replace(".eval", "")
            if method in METHOD_KEYS:
                out.setdefault(pid, {})[method] = d
    return out


def load_deberta_evals() -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for paper_dir in sorted((EVAL_ROOT / "evals_deberta").iterdir()):
        if not paper_dir.is_dir():
            continue
        pid = paper_dir.name
        for ep in paper_dir.glob("*.eval.json"):
            try:
                d = json.loads(ep.read_text())
            except Exception:
                continue
            if d.get("error"):
                continue
            if d.get("paper_recall", -1) == 0.0 and d.get("evidence_coverage", 0) > 0:
                continue
            method = ep.stem.replace(".eval", "")
            if method in METHOD_KEYS:
                out.setdefault(pid, {})[method] = d
    return out


# ---------------------------------------------------------------- stats

def cohens_d(a: Sequence[float], b: Sequence[float]) -> float:
    """Cohen's d for paired samples uses paired difference / std of difference.

    For unpaired pooled-std definition: d = (mean_A - mean_B) / pooled_std.
    For paired (which we have — same papers): d = mean(d_i) / std(d_i).
    """
    diffs = [ai - bi for ai, bi in zip(a, b)]
    mu = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    return mu / sd if sd > 0 else 0.0


def paired_bootstrap_ci(
    a: Sequence[float], b: Sequence[float],
    iters: int = 10_000, seed: int = 42, ci: float = 0.95,
) -> tuple[float, float, float]:
    """Returns (mean_diff, ci_low, ci_high) for paired diff a - b."""
    diffs = np.array([ai - bi for ai, bi in zip(a, b)])
    rng = np.random.default_rng(seed)
    n = len(diffs)
    boot_means = np.empty(iters)
    for i in range(iters):
        sample = diffs[rng.integers(0, n, size=n)]
        boot_means[i] = sample.mean()
    alpha = (1 - ci) / 2
    lo = float(np.quantile(boot_means, alpha))
    hi = float(np.quantile(boot_means, 1 - alpha))
    return float(diffs.mean()), lo, hi


def win_loss_tie(
    a: Sequence[float], b: Sequence[float], tol: float = 0.02,
) -> tuple[int, int, int]:
    wins = losses = ties = 0
    for ai, bi in zip(a, b):
        d = ai - bi
        if d > tol:
            wins += 1
        elif d < -tol:
            losses += 1
        else:
            ties += 1
    return wins, losses, ties


# ---------------------------------------------------------------- main


def compute_per_method_stats(strict: dict, deberta: dict) -> dict:
    out: dict[str, dict] = {}
    for m in METHOD_KEYS:
        s_f1 = [strict[p][m]["f1"] for p in sorted(strict.keys()) if m in strict[p]]
        d_f1 = [deberta[p][m]["f1"] for p in sorted(deberta.keys()) if m in deberta[p]]
        s_p  = [strict[p][m]["evidence_coverage"] for p in sorted(strict.keys()) if m in strict[p]]
        s_r  = [strict[p][m]["paper_recall"] for p in sorted(strict.keys()) if m in strict[p]]
        out[m] = {
            "n": len(s_f1),
            "strict_mean_f1": statistics.mean(s_f1) if s_f1 else 0,
            "strict_std_f1": statistics.stdev(s_f1) if len(s_f1) > 1 else 0,
            "strict_mean_p": statistics.mean(s_p) if s_p else 0,
            "strict_std_p": statistics.stdev(s_p) if len(s_p) > 1 else 0,
            "strict_mean_r": statistics.mean(s_r) if s_r else 0,
            "strict_std_r": statistics.stdev(s_r) if len(s_r) > 1 else 0,
            "deberta_mean_f1": statistics.mean(d_f1) if d_f1 else 0,
            "deberta_std_f1": statistics.stdev(d_f1) if len(d_f1) > 1 else 0,
        }
    return out


def compute_paired_diffs(strict: dict, deberta: dict) -> dict:
    """For Ours vs each baseline, compute paired diffs with CI + Cohen's d + win/loss."""
    out: dict[str, dict] = {}
    for baseline in METHOD_KEYS[1:]:  # skip Ours
        # Strict-LLM
        common = sorted(set(strict.keys()) & set(deberta.keys()))
        ours_s = []
        bl_s = []
        ours_d = []
        bl_d = []
        per_paper = []
        for pid in common:
            if "Ours" not in strict[pid] or baseline not in strict[pid]:
                continue
            if "Ours" not in deberta[pid] or baseline not in deberta[pid]:
                continue
            os_, bs_ = strict[pid]["Ours"]["f1"], strict[pid][baseline]["f1"]
            od_, bd_ = deberta[pid]["Ours"]["f1"], deberta[pid][baseline]["f1"]
            ours_s.append(os_); bl_s.append(bs_)
            ours_d.append(od_); bl_d.append(bd_)
            per_paper.append({"paper": pid, "ours_strict": os_, "bl_strict": bs_,
                              "ours_deberta": od_, "bl_deberta": bd_})

        if not ours_s:
            continue
        m_diff_s, lo_s, hi_s = paired_bootstrap_ci(ours_s, bl_s)
        m_diff_d, lo_d, hi_d = paired_bootstrap_ci(ours_d, bl_d)
        d_strict = cohens_d(ours_s, bl_s)
        d_deberta = cohens_d(ours_d, bl_d)
        wls_s = win_loss_tie(ours_s, bl_s)
        wls_d = win_loss_tie(ours_d, bl_d)

        out[f"Ours_vs_{baseline}"] = {
            "n": len(ours_s),
            "strict": {
                "mean_diff": round(m_diff_s, 4),
                "ci95_low": round(lo_s, 4),
                "ci95_high": round(hi_s, 4),
                "cohens_d": round(d_strict, 3),
                "ours_wins": wls_s[0],
                "ours_losses": wls_s[1],
                "ties": wls_s[2],
                "win_rate": round(wls_s[0] / sum(wls_s), 3),
            },
            "deberta": {
                "mean_diff": round(m_diff_d, 4),
                "ci95_low": round(lo_d, 4),
                "ci95_high": round(hi_d, 4),
                "cohens_d": round(d_deberta, 3),
                "ours_wins": wls_d[0],
                "ours_losses": wls_d[1],
                "ties": wls_d[2],
                "win_rate": round(wls_d[0] / sum(wls_d), 3),
            },
            "per_paper": per_paper,
        }
    return out


def issue_type_distribution() -> dict:
    """How often does each verifier issue type fire across the 29 strict runs?
    This is M2 evidence: if missing_info is ~5% it's the dominant gap; if ~30%
    it's not the missing mechanism. Note: in v1 we don't have coverage_gap yet.
    """
    counts = {
        "factual_error": 0,
        "missing_info": 0,
        "inconsistency": 0,
        "unsupported_claim": 0,
        "ambiguity": 0,
    }
    total_issues = 0
    # Issue lists are stored INSIDE the RefinedSummarization Ours.json under
    # adjudicator_data is gone; we have the strict eval per_claim. But the
    # ORIGINAL verifier issue types are reported by the RefinedSummarization
    # pipeline metadata — which we DON'T have stored separately. Best proxy:
    # look at the FinalSummary JSON's metadata to count `issues_addressed`.
    # However, types aren't stored.
    #
    # Workaround: load the Ours.json summary files which have FinalSummary
    # metadata.issues_raised + issues_addressed. But not the *types*.
    #
    # If types aren't stored, return what we can and a note.
    return {
        "note": "v1 RefinedSummarization stored issues_raised/issues_addressed counts but not per-type breakdown. M2 evidence requires re-run with logging.",
        "by_paper": {},
    }


# Try to load Ours.json metadata for issues_raised counts as proxy
def issue_count_proxy() -> dict:
    out: list[dict] = []
    sum_dir = EVAL_ROOT / "summaries"
    for paper_dir in sorted(sum_dir.iterdir()):
        if not paper_dir.is_dir():
            continue
        ours_json = paper_dir / "Ours.json"
        if not ours_json.exists():
            continue
        try:
            d = json.loads(ours_json.read_text())
            md = d.get("metadata", {})
            out.append({
                "paper": paper_dir.name,
                "issues_raised": md.get("issues_raised", 0),
                "issues_addressed_count": len(md.get("issues_addressed", [])),
                "evidence_paragraphs_used": len(md.get("evidence_paragraphs_used", [])),
                "consensus_breakdown": md.get("consensus_breakdown", {}),
            })
        except Exception:
            continue
    return {
        "per_paper": out,
        "mean_issues_raised": statistics.mean(r["issues_raised"] for r in out) if out else 0,
        "mean_issues_addressed": statistics.mean(r["issues_addressed_count"] for r in out) if out else 0,
    }


def find_largest_gap_papers(strict: dict, top_k: int = 3) -> list[dict]:
    """For M1 case study: papers where Ours F1 is most below B2 F1."""
    diffs = []
    for pid, ms in strict.items():
        if "Ours" not in ms or "B2_qwen_naive" not in ms:
            continue
        d = ms["Ours"]["f1"] - ms["B2_qwen_naive"]["f1"]
        diffs.append({
            "paper": pid,
            "title": ms["Ours"].get("title", pid)[:60],
            "ours_f1": round(ms["Ours"]["f1"], 3),
            "b2_f1": round(ms["B2_qwen_naive"]["f1"], 3),
            "diff": round(d, 3),
            "ours_p": round(ms["Ours"]["evidence_coverage"], 3),
            "b2_p": round(ms["B2_qwen_naive"]["evidence_coverage"], 3),
            "ours_r": round(ms["Ours"]["paper_recall"], 3),
            "b2_r": round(ms["B2_qwen_naive"]["paper_recall"], 3),
            "ours_claims": ms["Ours"]["total_claims"],
            "b2_claims": ms["B2_qwen_naive"]["total_claims"],
            "paper_claims": ms["Ours"]["paper_total_claims"],
        })
    diffs.sort(key=lambda x: x["diff"])
    return diffs[:top_k]


# ---------------------------------------------------------------- plotting


def plot_per_paper_scatter(strict: dict, out_path: Path) -> None:
    """One panel per baseline showing per-paper F1 (Ours vs Bk)."""
    baselines = METHOD_KEYS[1:]
    fig, axes = plt.subplots(2, 3, figsize=(13, 8))
    axes = axes.flatten()
    for ax, b in zip(axes, baselines):
        x, y = [], []
        for pid in sorted(strict.keys()):
            if "Ours" in strict[pid] and b in strict[pid]:
                x.append(strict[pid][b]["f1"])
                y.append(strict[pid]["Ours"]["f1"])
        ax.scatter(x, y, alpha=0.7, edgecolors="white", s=60, color="#1565C0")
        max_v = max(max(x), max(y), 0.7) + 0.05
        ax.plot([0, max_v], [0, max_v], "--", color="#888", linewidth=1)
        ax.fill_between([0, max_v], [0, max_v], [max_v, max_v], color="#C8E6C9", alpha=0.3, label="Ours wins")
        ax.fill_between([0, max_v], [0, 0], [0, max_v], color="#FFCDD2", alpha=0.3, label="Ours loses")
        wins, losses, ties = win_loss_tie(y, x)
        ax.set_xlabel(f"{METHOD_LABELS[b]} F1")
        ax.set_ylabel("Ours F1")
        ax.set_title(f"vs {METHOD_LABELS[b]}: W/L/T = {wins}/{losses}/{ties}")
        ax.set_xlim(0, max_v)
        ax.set_ylim(0, max_v)
        ax.grid(alpha=0.3)
    fig.suptitle("Per-paper F1 (strict-LLM): Ours vs each baseline. Dashed = tie line.\n"
                 "Above diagonal = Ours wins on that paper. Each dot = one of n=29 papers.",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_diff_distribution(strict: dict, out_path: Path) -> None:
    """Histogram of F1(Ours)-F1(B2) per paper."""
    diffs = []
    for pid in sorted(strict.keys()):
        if "Ours" in strict[pid] and "B2_qwen_naive" in strict[pid]:
            diffs.append(strict[pid]["Ours"]["f1"] - strict[pid]["B2_qwen_naive"]["f1"])
    if not diffs:
        return
    arr = np.array(diffs)
    mean_d = arr.mean()
    md, lo, hi = paired_bootstrap_ci(
        [strict[p]["Ours"]["f1"] for p in sorted(strict.keys())
         if "Ours" in strict[p] and "B2_qwen_naive" in strict[p]],
        [strict[p]["B2_qwen_naive"]["f1"] for p in sorted(strict.keys())
         if "Ours" in strict[p] and "B2_qwen_naive" in strict[p]],
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(arr, bins=20, color="#1565C0", edgecolor="white", alpha=0.85)
    ax.axvline(0, color="#444", linestyle="-", linewidth=1.5, label="0 (tie)")
    ax.axvline(mean_d, color="#C62828", linestyle="--", linewidth=2,
               label=f"mean = {mean_d:+.3f}")
    ax.axvspan(lo, hi, color="#FFCDD2", alpha=0.4,
               label=f"95% bootstrap CI = [{lo:+.3f}, {hi:+.3f}]")
    ax.set_xlabel("F1(Ours) − F1(B2 Qwen-72B-naive)  per paper")
    ax.set_ylabel("# papers (out of 29)")
    ax.set_title(
        "Per-paper F1 difference, strict-LLM mode. Negative = B2 wins on that paper.\n"
        f"Cohen's d = {cohens_d([strict[p]['Ours']['f1'] for p in sorted(strict.keys()) if 'Ours' in strict[p] and 'B2_qwen_naive' in strict[p]], [strict[p]['B2_qwen_naive']['f1'] for p in sorted(strict.keys()) if 'Ours' in strict[p] and 'B2_qwen_naive' in strict[p]]):.2f}",
        fontsize=10,
    )
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    strict = load_strict_evals()
    deberta = load_deberta_evals()
    print(f"Loaded {len(strict)} strict-LLM evals, {len(deberta)} DeBERTa evals.")

    per_method = compute_per_method_stats(strict, deberta)
    paired = compute_paired_diffs(strict, deberta)
    proxy = issue_count_proxy()
    case_studies = find_largest_gap_papers(strict, top_k=5)

    out = {
        "n_papers_strict": len(strict),
        "n_papers_deberta": len(deberta),
        "per_method": per_method,
        "paired_diffs_Ours_vs": paired,
        "issue_count_proxy": proxy,
        "case_studies_largest_gap_vs_B2": case_studies,
    }
    (PLOTS / "_stats.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {PLOTS / '_stats.json'}")

    plot_per_paper_scatter(strict, PLOTS / "_per_paper_scatter.png")
    print(f"wrote {PLOTS / '_per_paper_scatter.png'}")
    plot_diff_distribution(strict, PLOTS / "_diff_distribution.png")
    print(f"wrote {PLOTS / '_diff_distribution.png'}")


if __name__ == "__main__":
    main()
