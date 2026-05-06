"""Generate charts from outputs/experiment/evals/ or evals_strict/.

Produces (per --mode):
  - outputs/experiment/plots[_strict]/<arxiv_id>.png   (one per paper)
  - outputs/experiment/plots[_strict]/_mean.png        (average across papers)
  - outputs/experiment/plots[_strict]/_summary.csv     (table of all numbers)

Loose mode shows 2 bars per method: evidence_coverage + hallucination_rate.
Strict mode shows 4 bars per method: precision + recall + F1 + hallucination.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, pstdev

import matplotlib.pyplot as plt
import numpy as np

EVAL_ROOT = Path(__file__).resolve().parents[1]
OUT = EVAL_ROOT / "outputs" / "experiment"

# Method order (left → right on x-axis). Ours first so it stands out.
METHOD_ORDER = [
    "Ours",
    "B1_llama_naive",
    "B2_qwen_naive",
    "B3_deepseek_naive",
    "B4_llama8b_naive",
    "B5_llama_structured",
]
METHOD_LABELS = {
    "Ours": "Ours\n(3-LLM debate\n+RAG)",
    "B1_llama_naive": "B1\nLlama-70B\nnaive",
    "B2_qwen_naive": "B2\nQwen-72B\nnaive",
    "B3_deepseek_naive": "B3\nDeepSeek-V3\nnaive",
    "B4_llama8b_naive": "B4\nLlama-8B\nnaive",
    "B5_llama_structured": "B5\nLlama-70B\nstructured",
}

COVERAGE_COLOR = "#2E7D32"      # green
HALLUCINATION_COLOR = "#C62828"  # red
RECALL_COLOR = "#EF6C00"        # orange
F1_COLOR = "#1565C0"            # blue
OURS_HIGHLIGHT = "#0D47A1"      # darker blue (x-axis label accent)


def load_evals(arxiv_id: str, evals_dir: Path) -> dict[str, dict]:
    """Return {method_name: report_dict} for one paper. Skip error stubs."""
    out: dict[str, dict] = {}
    eval_dir = evals_dir / arxiv_id
    if not eval_dir.exists():
        return out
    for p in eval_dir.glob("*.eval.json"):
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if data.get("error"):
            continue
        method = p.stem.replace(".eval", "")
        out[method] = data
    return out


def plot_paper(arxiv_id: str, evals: dict[str, dict], out_path: Path, strict: bool) -> None:
    methods = [m for m in METHOD_ORDER if m in evals]
    if not methods:
        return
    title_text = evals[methods[0]].get("title") or arxiv_id
    if len(title_text) > 60:
        title_text = title_text[:57] + "…"

    if strict:
        # 4 bars: precision, recall, F1, hallucination
        precision = [evals[m]["evidence_coverage"] for m in methods]
        recall = [evals[m].get("paper_recall", 0.0) for m in methods]
        f1 = [evals[m].get("f1", 0.0) for m in methods]
        hallucination = [evals[m]["hallucination_rate"] for m in methods]

        x = np.arange(len(methods))
        w = 0.20
        fig, ax = plt.subplots(figsize=(12, 6))
        bars_pre = ax.bar(x - 1.5 * w, precision, w, color=COVERAGE_COLOR, label="Precision ↑")
        bars_rec = ax.bar(x - 0.5 * w, recall, w, color=RECALL_COLOR, label="Paper Recall ↑")
        bars_f1 = ax.bar(x + 0.5 * w, f1, w, color=F1_COLOR, label="F1 ↑")
        bars_hal = ax.bar(x + 1.5 * w, hallucination, w, color=HALLUCINATION_COLOR, label="Hallucination ↓")
        all_bars = [bars_pre, bars_rec, bars_f1, bars_hal]
    else:
        # 2 bars: coverage + hallucination
        coverage = [evals[m]["evidence_coverage"] for m in methods]
        hallucination = [evals[m]["hallucination_rate"] for m in methods]
        x = np.arange(len(methods))
        w = 0.38
        fig, ax = plt.subplots(figsize=(10, 5.5))
        bars_cov = ax.bar(x - w / 2, coverage, w, color=COVERAGE_COLOR, label="Evidence Coverage ↑")
        bars_hal = ax.bar(x + w / 2, hallucination, w, color=HALLUCINATION_COLOR, label="Hallucination Rate ↓")
        all_bars = [bars_cov, bars_hal]

    # Value labels on each bar
    for bars in all_bars:
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.01,
                f"{h:.2f}",
                ha="center", va="bottom",
                fontsize=8 if strict else 9,
            )

    ax.set_xticks(x)
    # Append claim counts (summary + paper) to each method label
    if strict:
        labels = [
            f"{METHOD_LABELS.get(m, m)}\n"
            f"(sum {evals[m]['total_claims']} | "
            f"paper {evals[m].get('paper_total_claims', '?')})"
            for m in methods
        ]
    else:
        labels = [
            f"{METHOD_LABELS.get(m, m)}\n({evals[m]['total_claims']} claims)"
            for m in methods
        ]
    ax.set_xticklabels(labels, fontsize=9)
    for i, m in enumerate(methods):
        if m == "Ours":
            ax.get_xticklabels()[i].set_color(OURS_HIGHLIGHT)
            ax.get_xticklabels()[i].set_fontweight("bold")

    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score (0–1)")
    title = (
        f"arXiv {arxiv_id}: {title_text}\n"
        + (
            "Strict: F1 = 2·precision·recall/(precision+recall) is the headline metric"
            if strict else
            "Loose: Coverage = supported/total_summary_claims (no paper-side recall)"
        )
    )
    ax.set_title(title, fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_mean(
    per_paper_evals: dict[str, dict[str, dict]],
    out_path: Path,
    strict: bool,
) -> None:
    """Aggregate across papers, plot grouped bars with std-dev error bars."""
    metric_keys: list[tuple[str, str, str]]  # (field, label, color)
    if strict:
        metric_keys = [
            ("evidence_coverage", "Precision ↑", COVERAGE_COLOR),
            ("paper_recall",      "Paper Recall ↑", RECALL_COLOR),
            ("f1",                "F1 ↑", F1_COLOR),
            ("hallucination_rate","Hallucination ↓", HALLUCINATION_COLOR),
        ]
    else:
        metric_keys = [
            ("evidence_coverage", "Evidence Coverage ↑", COVERAGE_COLOR),
            ("hallucination_rate","Hallucination Rate ↓", HALLUCINATION_COLOR),
        ]

    # Collect per-method, per-metric arrays.
    per_method: dict[str, dict[str, list[float]]] = {
        m: {k[0]: [] for k in metric_keys} for m in METHOD_ORDER
    }
    for arxiv_id, evals in per_paper_evals.items():
        for m in METHOD_ORDER:
            if m in evals:
                for field, _, _ in metric_keys:
                    per_method[m][field].append(evals[m].get(field, 0.0))

    methods = [m for m in METHOD_ORDER if per_method[m][metric_keys[0][0]]]
    n_papers = len(per_paper_evals)
    n_metrics = len(metric_keys)
    x = np.arange(len(methods))
    bar_width = 0.85 / n_metrics

    fig, ax = plt.subplots(figsize=(12, 6))
    for i, (field, label, color) in enumerate(metric_keys):
        means = [mean(per_method[m][field]) for m in methods]
        stds = [
            pstdev(per_method[m][field]) if len(per_method[m][field]) > 1 else 0
            for m in methods
        ]
        offset = (i - (n_metrics - 1) / 2) * bar_width
        bars = ax.bar(x + offset, means, bar_width, yerr=stds, color=color,
                      label=label, capsize=3)
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.01,
                f"{h:.2f}",
                ha="center", va="bottom", fontsize=8, fontweight="bold",
            )

    ax.set_xticks(x)
    # Mean claim counts in label
    if strict:
        mean_sum_claims = [
            round(mean([evals[m]["total_claims"]
                        for evals in per_paper_evals.values() if m in evals]))
            for m in methods
        ]
        mean_paper_claims = [
            round(mean([evals[m].get("paper_total_claims", 0)
                        for evals in per_paper_evals.values() if m in evals]))
            for m in methods
        ]
        labels = [
            f"{METHOD_LABELS.get(m, m)}\n"
            f"(mean sum {sc} | paper {pc})"
            for m, sc, pc in zip(methods, mean_sum_claims, mean_paper_claims)
        ]
    else:
        mean_claims = [
            round(mean([evals[m]["total_claims"]
                        for evals in per_paper_evals.values() if m in evals]))
            for m in methods
        ]
        labels = [
            f"{METHOD_LABELS.get(m, m)}\n(mean {n} claims)"
            for m, n in zip(methods, mean_claims)
        ]
    ax.set_xticklabels(labels, fontsize=9)
    for i, m in enumerate(methods):
        if m == "Ours":
            ax.get_xticklabels()[i].set_color(OURS_HIGHLIGHT)
            ax.get_xticklabels()[i].set_fontweight("bold")

    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score (0–1)")
    title_suffix = (
        "F1 = 2·precision·recall/(precision+recall) is the headline metric"
        if strict else
        "Higher coverage + lower hallucination = better summary"
    )
    ax.set_title(
        f"Mean across {n_papers} papers ({'strict' if strict else 'loose'} eval, "
        f"error bars = population std-dev)\n{title_suffix}",
        fontsize=11,
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="upper right", fontsize=9, ncol=n_metrics // 2 if n_metrics > 2 else 1)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_summary_csv(
    per_paper_evals: dict[str, dict[str, dict]], out_path: Path, strict: bool
) -> None:
    if strict:
        header = (
            "paper,method,precision,recall,f1,hallucination,"
            "supported,partial,unsupported,contradicted,total_summary,"
            "covered,partial_recall,not_covered,total_paper"
        )
    else:
        header = "paper,method,coverage,hallucination,supported,partial,unsupported,contradicted,total"
    rows = [header]
    for arxiv_id, evals in sorted(per_paper_evals.items()):
        for m in METHOD_ORDER:
            if m not in evals:
                continue
            r = evals[m]
            c = r.get("counts", {})
            if strict:
                pc = r.get("paper_coverage_counts", {})
                rows.append(
                    f"{arxiv_id},{m},"
                    f"{r['evidence_coverage']:.4f},"
                    f"{r.get('paper_recall',0):.4f},"
                    f"{r.get('f1',0):.4f},"
                    f"{r['hallucination_rate']:.4f},"
                    f"{c.get('supported',0)},{c.get('partial',0)},"
                    f"{c.get('unsupported',0)},{c.get('contradicted',0)},"
                    f"{r['total_claims']},"
                    f"{pc.get('covered',0)},{pc.get('partial',0)},"
                    f"{pc.get('not_covered',0)},{r.get('paper_total_claims',0)}"
                )
            else:
                rows.append(
                    f"{arxiv_id},{m},"
                    f"{r['evidence_coverage']:.4f},{r['hallucination_rate']:.4f},"
                    f"{c.get('supported',0)},{c.get('partial',0)},"
                    f"{c.get('unsupported',0)},{c.get('contradicted',0)},"
                    f"{r['total_claims']}"
                )
    out_path.write_text("\n".join(rows) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["loose", "strict", "deberta"],
        default="loose",
        help="loose:    outputs/experiment/evals/        → plots/\n"
             "strict:   outputs/experiment/evals_strict/ → plots_strict/\n"
             "deberta:  outputs/experiment/evals_deberta/→ plots_deberta/",
    )
    args = parser.parse_args()
    is_strict_layout = args.mode in ("strict", "deberta")

    if args.mode == "loose":
        evals_dir = OUT / "evals"
        plots_dir = OUT / "plots"
    elif args.mode == "strict":
        evals_dir = OUT / "evals_strict"
        plots_dir = OUT / "plots_strict"
    else:  # deberta
        evals_dir = OUT / "evals_deberta"
        plots_dir = OUT / "plots_deberta"
    plots_dir.mkdir(parents=True, exist_ok=True)
    strict = is_strict_layout  # both strict and deberta use the 4-bar layout

    paper_ids = sorted(p.name for p in evals_dir.iterdir() if p.is_dir())
    if not paper_ids:
        print(f"No eval results found in {evals_dir}", file=sys.stderr)
        sys.exit(1)

    per_paper: dict[str, dict[str, dict]] = {}
    for pid in paper_ids:
        evals = load_evals(pid, evals_dir)
        if not evals:
            continue
        per_paper[pid] = evals
        plot_paper(pid, evals, plots_dir / f"{pid}.png", strict=strict)
        print(f"wrote {plots_dir.name}/{pid}.png ({len(evals)} methods)")

    if per_paper:
        plot_mean(per_paper, plots_dir / "_mean.png", strict=strict)
        print(f"wrote {plots_dir.name}/_mean.png (n={len(per_paper)} papers)")
        write_summary_csv(per_paper, plots_dir / "_summary.csv", strict=strict)
        print(f"wrote {plots_dir.name}/_summary.csv")


if __name__ == "__main__":
    main()
