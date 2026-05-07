"""Render headline figures for the OneVision n=15 experiment.

Outputs (into RefinedSummarization/paper/figures/):
  onevision_means.png      — 7 methods × {F1, F0.5, R} per evaluator (bars + CI)
  onevision_contrasts.png  — paired Δ(Ours_onevision − baseline) for each baseline
  onevision_lengths.png    — actual word counts per method (boxplot) — sanity check on length parity
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

EVAL_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "experiment"
FIG_DIR = (
    Path(__file__).resolve().parents[2]
    / "RefinedSummarization" / "paper" / "figures"
)
FIG_DIR.mkdir(parents=True, exist_ok=True)

METHODS = [
    "Ours_onevision",
    "B1_llama_naive",
    "B2_qwen_naive",
    "B3_deepseek_naive",
    "B4_llama8b_naive",
    "B5_llama_structured",
    "B6_llama_v2prompt",
]
METHOD_LABELS = {
    "Ours_onevision":      "Ours\nOneVision",
    "B1_llama_naive":      "B1\nLlama-naive",
    "B2_qwen_naive":       "B2\nQwen-naive",
    "B3_deepseek_naive":   "B3\nDeepSeek\nnaive",
    "B4_llama8b_naive":    "B4\nLlama-8B\nnaive",
    "B5_llama_structured": "B5\nLlama\nstructured",
    "B6_llama_v2prompt":   "B6\nLlama\nv2-prompt",
}
COLORS = ["#2e7d32", "#888888", "#a05a2c", "#5b3299", "#bbbbbb", "#666666", "#5b9bd5"]


def boot_ci(values: list[float], iters: int = 10_000, seed: int = 42):
    arr = np.array(values)
    rng = np.random.default_rng(seed)
    boot = np.array([
        arr[rng.integers(0, len(arr), size=len(arr))].mean()
        for _ in range(iters)
    ])
    return float(arr.mean()), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def load_summary() -> dict:
    p = EVAL_ROOT / "onevision_summary.json"
    return json.loads(p.read_text())


# ---------- per-paper raw values for CIs ----------
def per_paper_metric(eval_dir: str, papers: list[str], method: str, key: str) -> list[float]:
    out: list[float] = []
    for pid in papers:
        f = EVAL_ROOT / eval_dir / pid / f"{method}.eval.json"
        if not f.exists():
            continue
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if d.get("error"):
            continue
        if d.get("paper_recall", -1) == 0.0 and d.get("evidence_coverage", 0) > 0:
            continue
        v = d.get(key)
        if v is None:
            continue
        out.append(float(v))
    return out


def per_paper_words(papers: list[str], method: str) -> list[int]:
    out: list[int] = []
    for pid in papers:
        sum_dir = EVAL_ROOT / "summaries" / pid
        md = sum_dir / f"{method}.md"
        js = sum_dir / f"{method}.json"
        if md.exists():
            out.append(len(md.read_text().split()))
        elif js.exists():
            try:
                d = json.loads(js.read_text())
            except Exception:
                continue
            if d.get("error"):
                continue
            n = 0
            for k in ("tldr", "core_idea"):
                v = d.get(k) or ""
                n += len(v.split())
            for c in d.get("key_contributions") or []:
                n += len((c.get("text") if isinstance(c, dict) else str(c)).split())
            m = d.get("method") or {}
            n += len((m.get("overview") or "").split())
            for comp in m.get("components") or []:
                n += len((comp.get("name") or "").split())
                n += len((comp.get("description") or "").split())
            e = d.get("experiments") or {}
            n += len((e.get("setup") or "").split())
            for f_ in e.get("key_findings") or []:
                n += len((f_.get("text") if isinstance(f_, dict) else str(f_)).split())
            for lim in d.get("limitations") or []:
                n += len((lim if isinstance(lim, str) else "").split())
            out.append(n)
    return out


def draw_means(papers_by_mode: dict[str, list[str]]) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 7), sharex=False)
    for col, (mode_name, eval_dir) in enumerate([
        ("Strict-LLM",  "evals_strict"),
        ("DeBERTa-NLI", "evals_deberta"),
        ("DeBERTa-NLI", "evals_deberta"),  # placeholder; we do a 2x3 (rows=metric, cols=mode)
    ]):
        pass  # we'll redo layout

    # Better layout: 1 row × 3 metrics, each subplot has 2 modes side by side.
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), sharey=False)
    metrics = [
        ("F1",   "f1"),
        ("F0.5", "f_half"),
        ("Recall", "paper_recall"),
    ]
    bar_w = 0.35
    x = np.arange(len(METHODS))
    for ax, (mlabel, mkey) in zip(axes, metrics):
        for i, (mode_name, eval_dir) in enumerate([
            ("Strict",   "evals_strict"),
            ("DeBERTa",  "evals_deberta"),
        ]):
            offset = (i - 0.5) * bar_w
            means = []
            errs_lo = []
            errs_hi = []
            for m in METHODS:
                vals = per_paper_metric(eval_dir, papers_by_mode.get(eval_dir, []), m, mkey)
                if not vals:
                    means.append(0); errs_lo.append(0); errs_hi.append(0); continue
                mu, lo, hi = boot_ci(vals)
                means.append(mu); errs_lo.append(mu - lo); errs_hi.append(hi - mu)
            ax.bar(
                x + offset, means, bar_w,
                yerr=[errs_lo, errs_hi], capsize=3,
                label=mode_name,
                color="#2e7d32" if mode_name == "Strict" else "#5b9bd5",
                alpha=0.85, edgecolor="black",
            )
        ax.set_xticks(x)
        ax.set_xticklabels([METHOD_LABELS[m] for m in METHODS], fontsize=8)
        ax.set_ylabel(mlabel)
        ax.set_title(mlabel)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)
    n_strict = len(papers_by_mode.get("evals_strict", []))
    n_deberta = len(papers_by_mode.get("evals_deberta", []))
    fig.suptitle(f"OneVision (n={max(n_strict, n_deberta)}): mean F1 / F0.5 / Recall per method, two evaluators", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "onevision_means.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def draw_contrasts(papers_by_mode: dict[str, list[str]]) -> None:
    """One panel per evaluator. Bar = Δ(OneVision − baseline) on F1, error bar = 95% CI."""
    baselines = METHODS[1:]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    for ax, (mode_name, eval_dir) in zip(axes, [
        ("Strict-LLM",  "evals_strict"),
        ("DeBERTa-NLI", "evals_deberta"),
    ]):
        means = []; errs_lo = []; errs_hi = []
        for m in baselines:
            ov_vals = per_paper_metric(eval_dir, papers_by_mode.get(eval_dir, []), "Ours_onevision", "f1")
            bl_vals = per_paper_metric(eval_dir, papers_by_mode.get(eval_dir, []), m, "f1")
            paper_set_ov = set(per_paper_metric.__defaults__ or [])  # not used; we recompute pairs below.
            # Recompute pairs directly:
            ov_per_paper = {}
            bl_per_paper = {}
            for pid in papers_by_mode.get(eval_dir, []):
                f = EVAL_ROOT / eval_dir / pid
                ov_p = f / "Ours_onevision.eval.json"
                bl_p = f / f"{m}.eval.json"
                def _f1(p):
                    try:
                        d = json.loads(p.read_text())
                        if d.get("error"): return None
                        if d.get("paper_recall", -1) == 0.0 and d.get("evidence_coverage", 0) > 0: return None
                        return d.get("f1")
                    except Exception:
                        return None
                if ov_p.exists() and bl_p.exists():
                    a = _f1(ov_p); b = _f1(bl_p)
                    if a is not None and b is not None:
                        ov_per_paper[pid] = a; bl_per_paper[pid] = b
            diffs = [ov_per_paper[k] - bl_per_paper[k] for k in ov_per_paper.keys() & bl_per_paper.keys()]
            if not diffs:
                means.append(0); errs_lo.append(0); errs_hi.append(0); continue
            mu, lo, hi = boot_ci(diffs)
            means.append(mu); errs_lo.append(mu - lo); errs_hi.append(hi - mu)
        x = np.arange(len(baselines))
        bars = ax.bar(x, means, yerr=[errs_lo, errs_hi], capsize=4,
                       color=["#888"]*len(baselines), edgecolor="black")
        # Color significant bars green (positive) / red (negative).
        for bar, mu, lo, hi in zip(bars, means, errs_lo, errs_hi):
            ci_lo = mu - lo; ci_hi = mu + hi  # absolute CI bounds
            if ci_lo > 0:    bar.set_facecolor("#2e7d32")
            elif ci_hi < 0:  bar.set_facecolor("#c62828")
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([METHOD_LABELS[m].replace("\n", " ") for m in baselines], fontsize=8, rotation=20, ha="right")
        ax.set_title(f"{mode_name}: ΔF1 (Ours_onevision − baseline)")
        ax.set_ylabel("ΔF1")
        ax.grid(axis="y", alpha=0.3)
        for xi, m in zip(x, means):
            ax.text(xi, m + 0.005 if m >= 0 else m - 0.015, f"{m:+.3f}", ha="center", fontsize=8)
    fig.suptitle("OneVision contrasts (paired Δ on F1 with 95% bootstrap CI)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "onevision_contrasts.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def draw_lengths(papers_by_mode: dict[str, list[str]]) -> None:
    """Box plot of summary word counts per method — sanity check that length is comparable."""
    # Use any paper set (lengths don't depend on evaluator).
    papers = papers_by_mode.get("evals_strict") or papers_by_mode.get("evals_deberta") or []
    fig, ax = plt.subplots(figsize=(11, 4))
    data = []
    for m in METHODS:
        ws = per_paper_words(papers, m)
        data.append(ws)
    bplot = ax.boxplot(data, labels=[METHOD_LABELS[m].replace("\n", " ") for m in METHODS],
                       showmeans=True, patch_artist=True)
    for patch, c in zip(bplot["boxes"], COLORS):
        patch.set_facecolor(c); patch.set_alpha(0.65)
    ax.axhline(1000, color="firebrick", linestyle="--", lw=1.0, label="hard cap = 1000")
    ax.set_ylabel("Summary length (words)")
    ax.set_title(f"Summary lengths per method (n≤{len(papers)} papers); cap = 1000 words")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "onevision_lengths.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    summary = load_summary()
    papers_by_mode = {
        "evals_strict":  summary.get("strict",  {}).get("papers_used", []),
        "evals_deberta": summary.get("deberta", {}).get("papers_used", []),
    }
    draw_means(papers_by_mode)
    draw_contrasts(papers_by_mode)
    draw_lengths(papers_by_mode)
    print("wrote 3 figures into", FIG_DIR)


if __name__ == "__main__":
    main()
