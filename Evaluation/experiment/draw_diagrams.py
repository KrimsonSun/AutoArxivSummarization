"""Render evaluation-pipeline flowcharts as PNG.

Outputs:
  outputs/experiment/plots/_pipeline_compare.png    (3-column side-by-side)
  outputs/experiment/plots/_pipeline_data_flow.png  (per-step LLM vs DeBERTa
                                                     vs CPU breakdown with
                                                     data shapes)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "outputs" / "experiment" / "plots"

# Color palette (consistent across diagrams)
LLM = "#FFE08A"        # yellow — expensive LLM call
NLI = "#FFCC80"        # orange — local NLI inference
CPU = "#B3E5FC"        # blue — pure CPU compute
DATA = "#E0E0E0"       # gray — data / cache
OUT_BOX = "#C8E6C9"    # green — output metric
EDGE = "#424242"       # dark gray box border
DELTA = "#EF5350"      # red — highlights what's different across modes
SAME = "#9E9E9E"       # gray dim — for "same as previous mode"


def add_box(
    ax, x, y, w, h, text, *,
    fill=DATA, edge=EDGE, fontsize=8.5, weight="normal",
    line_width=1.0,
):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=fill,
        edgecolor=edge,
        linewidth=line_width,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center",
        fontsize=fontsize, fontweight=weight,
        wrap=True,
    )


def add_arrow(ax, x1, y1, x2, y2, label=None, color=EDGE, lw=1.4):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>",
        mutation_scale=14,
        color=color,
        linewidth=lw,
    )
    ax.add_patch(a)
    if label:
        ax.text(
            (x1 + x2) / 2 + 0.05, (y1 + y2) / 2,
            label, fontsize=7, color=color, style="italic",
            ha="left", va="center",
        )


# ---------------------------------------------------------------- 3-column compare

def draw_compare():
    fig, ax = plt.subplots(figsize=(15, 11))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 14)
    ax.axis("off")

    # === COLUMN HEADERS ===
    header_y = 13
    column_w = 4.4
    column_xs = [0.5, 5.3, 10.1]  # left edges of 3 columns

    headers = ["LOOSE", "STRICT-LLM", "DeBERTa-NLI"]
    header_colors = [LLM, LLM, NLI]
    for x, hdr, col in zip(column_xs, headers, header_colors):
        add_box(
            ax, x, header_y, column_w, 0.7, hdr,
            fill=col, fontsize=14, weight="bold", line_width=2,
        )

    # === ROW: Step 1 — Summary claim extraction (SAME) ===
    y = 11.5
    for x in column_xs:
        add_box(
            ax, x, y, column_w, 0.9,
            "Step 1\nSummary → atomic claims\nLLM (Llama 70B)\noutput: ClaimList",
            fill=LLM, fontsize=8,
        )

    # === ROW: Step 2 — BM25 retrieval (SAME) ===
    y = 10.1
    for x in column_xs:
        add_box(
            ax, x, y, column_w, 0.9,
            "Step 2\nBM25 retrieval\nCPU, top-k=5\noutput: List[EvidenceChunk]",
            fill=CPU, fontsize=8,
        )

    # === ROW: Step 3 — Verification (DIFFERS) ===
    y = 8.7
    # Loose
    add_box(
        ax, column_xs[0], y, column_w, 0.9,
        "Step 3 (LOOSE)\nLLM verify, N parallel\nlenient prompt\n"
        "output: Verdict ∈ 4 classes",
        fill=LLM, fontsize=8, edge=DELTA, line_width=2,
    )
    # Strict-LLM
    add_box(
        ax, column_xs[1], y, column_w, 0.9,
        "Step 3 (STRICT)\nLLM verify, N parallel\nSTRICT prompt: # required,\n"
        "vague→Partial",
        fill=LLM, fontsize=8, edge=DELTA, line_width=2,
    )
    # DeBERTa
    add_box(
        ax, column_xs[2], y, column_w, 0.9,
        "Step 3 (DeBERTa)\nDeBERTa-v3 NLI, MPS\nentail/neutral/contra probs\n"
        "thresh: 0.70/0.30/0.50",
        fill=NLI, fontsize=8, edge=DELTA, line_width=2,
    )

    # === ROW: Step 4a — aggregate loose metrics (SAME) ===
    y = 7.3
    for x in column_xs:
        add_box(
            ax, x, y, column_w, 0.9,
            "Step 4a (Python)\nAggregate verdicts →\nprecision, hallucination",
            fill=CPU, fontsize=8,
        )

    # === ROW: Step 5 — Paper claim extraction (LOOSE skips) ===
    y = 5.9
    add_box(
        ax, column_xs[0], y, column_w, 0.9,
        "(SKIPPED)\nLoose has no\npaper-side recall",
        fill="#F5F5F5", fontsize=9, edge=SAME,
    )
    for x in column_xs[1:]:
        add_box(
            ax, x, y, column_w, 0.9,
            "Step 5\nPaper → atomic claims\nLLM, ONCE per paper, CACHED\noutput: PaperClaimList",
            fill=LLM, fontsize=8, edge=DELTA, line_width=2,
        )

    # === ROW: Step 6 — Recall check (LOOSE skips) ===
    y = 4.5
    add_box(
        ax, column_xs[0], y, column_w, 0.9,
        "(SKIPPED)",
        fill="#F5F5F5", fontsize=9, edge=SAME,
    )
    for x in column_xs[1:]:
        add_box(
            ax, x, y, column_w, 0.9,
            "Step 6\nFor each paper claim, ask\n"
            "LLM: covered by summary?\n"
            "1 batched call",
            fill=LLM, fontsize=8, edge=DELTA, line_width=2,
        )

    # === ROW: Step 4b — F1 (LOOSE skips) ===
    y = 3.1
    add_box(
        ax, column_xs[0], y, column_w, 0.9,
        "(no F1 in loose mode)",
        fill="#F5F5F5", fontsize=9, edge=SAME,
    )
    for x in column_xs[1:]:
        add_box(
            ax, x, y, column_w, 0.9,
            "Step 4b (Python)\nrecall = covered/total_paper\nF1 = 2·P·R/(P+R)",
            fill=CPU, fontsize=8,
        )

    # === OUTPUT ROW ===
    y = 1.7
    add_box(
        ax, column_xs[0], y, column_w, 0.8,
        "OUTPUT\n{ coverage,\n  hallucination_rate }",
        fill=OUT_BOX, fontsize=8.5, weight="bold",
    )
    for x in column_xs[1:]:
        add_box(
            ax, x, y, column_w, 0.8,
            "OUTPUT\n{ precision, hallucination,\n  paper_recall, F1 }",
            fill=OUT_BOX, fontsize=8.5, weight="bold",
        )

    # === COST/TIME footer ===
    y = 0.5
    footer = [
        "LLM calls/paper: 1+N (~26)\nTime: ~30s   Cost: ~$0.02",
        "LLM calls/paper: 2+N (~27)\nTime: ~2 min   Cost: ~$0.05",
        "LLM calls/paper: 2 + 0\nNLI inferences: ~125 (MPS)\nTime: ~1 min   Cost: ~$0.02",
    ]
    for x, txt in zip(column_xs, footer):
        ax.text(
            x + column_w / 2, y, txt,
            ha="center", va="center", fontsize=8.5,
            family="monospace",
        )

    # === Vertical down-arrows between rows in each column ===
    arrow_xs = [x + column_w / 2 for x in column_xs]
    arrow_y_pairs = [
        (12.4, 12.2), (11.5, 11.3), (10.1, 9.9),
        (8.7, 8.5), (7.3, 7.1), (5.9, 5.7),
        (4.5, 4.3), (3.1, 2.9),
    ]
    for arx in arrow_xs:
        for y1, y2 in arrow_y_pairs:
            add_arrow(ax, arx, y1, arx, y2, lw=1.0)

    # === LEGEND ===
    legend_y = 12.5
    legend_items = [
        (LLM, "LLM call (Llama 70B via OpenRouter)"),
        (NLI, "Local NLI (DeBERTa-v3, on MPS)"),
        (CPU, "Pure CPU computation"),
        (OUT_BOX, "Pipeline output"),
    ]
    legend_x = 0.5
    for i, (color, label) in enumerate(legend_items):
        add_box(ax, legend_x + i * 3.6, legend_y, 0.4, 0.3, "", fill=color, fontsize=6)
        ax.text(
            legend_x + i * 3.6 + 0.45, legend_y + 0.15, label,
            ha="left", va="center", fontsize=8,
        )
    ax.text(
        7.5, header_y + 1.0,
        "Three Evaluation Pipelines — same input (summary, paper), different verifier strictness",
        ha="center", fontsize=13, fontweight="bold",
    )

    # === DELTA highlight notes (right margin) ===
    ax.text(
        14.7, 9.15,
        "← differs:\n  prompt or model",
        fontsize=8, color=DELTA, ha="left", va="center", fontweight="bold",
    )
    ax.text(
        14.7, 6.35,
        "← absent in loose:\n  paper-side recall",
        fontsize=8, color=DELTA, ha="left", va="center", fontweight="bold",
    )

    fig.tight_layout()
    out_path = OUT / "_pipeline_compare.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------- per-step data flow

def draw_data_flow():
    """One detailed diagram showing data shapes between steps + concrete
    example values, focused on the strict pipeline (most informative)."""
    fig, ax = plt.subplots(figsize=(15, 10))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 11)
    ax.axis("off")

    ax.text(
        7.5, 10.5,
        "Strict / DeBERTa Pipeline — concrete data flow on one paper "
        "(DALL-E 2, Ours summary)",
        ha="center", fontsize=13, fontweight="bold",
    )

    # Boxes with concrete examples
    # Layout: steps on the left column, data shapes on the right
    step_x, step_w = 0.5, 5.5
    data_x, data_w = 6.5, 8.0
    h = 0.85

    rows = [
        # (step_text, fill, data_text, data_color)
        (
            "INPUT\n(summary, paper PDF)",
            DATA,
            "Ours.json (1.6 KB JSON, 6 fields)\npaper.pdf (4.2 MB, 77 paragraphs after parse)",
            DATA,
        ),
        (
            "Step 1 (LLM, ~10s)\nSummary → atomic claims\n"
            "Llama 70B on OpenRouter",
            LLM,
            "ClaimList (25 items):\n"
            "  C1: 'unCLIP achieves SOTA on text-to-image'\n"
            "  C2: 'The decoder is a 3.5B param diffusion model'\n"
            "  ... C25: 'CLIP score 0.341 on MS-COCO'",
            DATA,
        ),
        (
            "Step 2 (CPU, <1s)\nBM25 over paragraphs\n"
            "for each claim → top-5 paragraph IDs",
            CPU,
            "for C1: [P3 (s=14.2), P7 (s=11.8), P12, P15, P18]\n"
            "for C2: [P8 (s=12.5), P15, P22, P3, P14]\n"
            "...",
            DATA,
        ),
        (
            "Step 3 (LLM × 25 parallel, ~10s)\n"
            "STRICT prompt verifier\n"
            "or DeBERTa-NLI on MPS (~5s)",
            LLM,
            "ClaimVerification × 25:\n"
            "  C1 → Supported   (P(entail)=0.94)\n"
            "  C2 → Partial     (vague: '3.5B' missing in evidence)\n"
            "  C3 → Unsupported (no relevant evidence)\n"
            "  ...",
            DATA,
        ),
        (
            "Step 4a (Python)\n"
            "aggregate verdicts → precision",
            CPU,
            "counts: {Supported: 22, Partial: 0, Unsupported: 1, Contradicted: 2}\n"
            "evidence_coverage = (22 + 0.5×0)/25 = 0.88\n"
            "hallucination_rate = (1 + 2)/25 = 0.12",
            OUT_BOX,
        ),
        (
            "Step 5 (LLM, once-cached, ~50s)\n"
            "Paper → atomic claims\n"
            "shared across all 6 methods on this paper",
            LLM,
            "PaperClaimList (40 items):\n"
            "  PC1: 'unCLIP uses a CLIP image encoder' (P3)\n"
            "  PC2: 'Decoder has 3.5B parameters' (P8)\n"
            "  ... PC40: 'Trained on 250M image-text pairs' (P54)",
            DATA,
        ),
        (
            "Step 6 (LLM, 1 batched call, ~50s)\n"
            "for each PaperClaim, ask:\n"
            "is it covered by the summary text?",
            LLM,
            "PaperCoverageList × 40:\n"
            "  PC1 → Covered\n"
            "  PC2 → Partial\n"
            "  PC3 → NotCovered\n"
            "  ...",
            DATA,
        ),
        (
            "Step 4b (Python)\n"
            "compute recall + F1",
            CPU,
            "covered: 7, partial: 0, not_covered: 33 (total: 40)\n"
            "paper_recall = (7 + 0.5×0)/40 = 0.175\n"
            "F1 = 2 × 0.88 × 0.175 / (0.88 + 0.175) = 0.292",
            OUT_BOX,
        ),
        (
            "OUTPUT\nEvaluationReport JSON",
            OUT_BOX,
            "{ precision: 0.88, hallucination: 0.12,\n"
            "  paper_recall: 0.175, F1: 0.292,\n"
            "  per_claim: [25 verdicts],\n"
            "  per_paper_claim: [40 coverage verdicts] }",
            OUT_BOX,
        ),
    ]

    n = len(rows)
    y_top = 9.5
    y_step = (y_top - 0.5) / n

    for i, (step_text, step_fill, data_text, data_fill) in enumerate(rows):
        y = y_top - (i + 1) * y_step
        add_box(
            ax, step_x, y, step_w, h,
            step_text, fill=step_fill, fontsize=8.5,
        )
        add_box(
            ax, data_x, y, data_w, h,
            data_text, fill=data_fill, fontsize=7.5,
        )
        if i < n - 1:
            add_arrow(ax, step_x + step_w / 2, y, step_x + step_w / 2, y - 0.13, lw=1.4)
            add_arrow(ax, data_x + data_w / 2, y, data_x + data_w / 2, y - 0.13, lw=1.0, color=SAME)

    fig.tight_layout()
    out_path = OUT / "_pipeline_data_flow.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------- summary table

def draw_summary_table():
    """One PNG showing the final 3-mode results table (n=29, loaded fresh)."""
    import json
    import statistics
    from pathlib import Path

    EVAL_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "experiment"

    method_keys = ["Ours", "B1_llama_naive", "B2_qwen_naive",
                   "B3_deepseek_naive", "B4_llama8b_naive", "B5_llama_structured"]

    def load_mode(eval_dir_name: str) -> dict:
        out = {m: [] for m in method_keys}
        eval_dir = EVAL_ROOT / eval_dir_name
        if not eval_dir.exists():
            return out
        for paper_dir in eval_dir.iterdir():
            if not paper_dir.is_dir():
                continue
            for ep in paper_dir.glob("*.eval.json"):
                try:
                    d = json.loads(ep.read_text())
                except Exception:
                    continue
                if d.get("error"):
                    continue
                if eval_dir_name != "evals":
                    if d.get("paper_recall", -1) == 0.0 and d.get("evidence_coverage", 0) > 0:
                        continue
                m = ep.stem.replace(".eval", "")
                if m in out:
                    out[m].append(d)
        return out

    loose = load_mode("evals")
    strict = load_mode("evals_strict")
    deberta = load_mode("evals_deberta")

    def mn(rows, key):
        vals = [r.get(key, 0.0) for r in rows]
        return statistics.mean(vals) if vals else 0.0

    data = []
    for m in method_keys:
        data.append((
            mn(loose[m], "evidence_coverage"),
            mn(loose[m], "hallucination_rate"),
            mn(strict[m], "evidence_coverage"),
            mn(strict[m], "paper_recall"),
            mn(strict[m], "f1"),
            mn(deberta[m], "evidence_coverage"),
            mn(deberta[m], "paper_recall"),
            mn(deberta[m], "f1"),
            mn(deberta[m], "hallucination_rate"),
        ))

    # Determine winner = highest strict-LLM F1
    f1s = [d[4] for d in data]
    winner_idx = f1s.index(max(f1s))
    is_ours = [m == "Ours" for m in method_keys]
    is_winner = [i == winner_idx for i in range(len(method_keys))]

    # Determine n for header
    n_papers = max(len(loose[m]) for m in method_keys)

    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7)
    ax.axis("off")

    ax.text(
        6.5, 6.6,
        f"3-Mode Evaluation Results — mean across {n_papers} papers",
        ha="center", fontsize=14, fontweight="bold",
    )

    method_labels = [
        "Ours", "B1 Llama-70B", "B2 Qwen-72B",
        "B3 DeepSeek-V3", "B4 Llama-8B", "B5 Llama-struct",
    ]
    methods = method_labels  # rename for compatibility below

    headers_top = [
        ("Method", 0.5, 2.4),
        ("LOOSE", 2.9, 2.0),
        ("STRICT-LLM", 4.9, 3.2),
        ("DeBERTa-NLI", 8.1, 4.5),
    ]
    for label, x, w in headers_top:
        add_box(
            ax, x, 5.6, w, 0.4, label,
            fill="#FFB74D" if "STRICT" in label or "LOOSE" in label or "DeBERTa" in label else "#90A4AE",
            fontsize=10, weight="bold",
        )
    headers_bot = [
        ("cov", 2.9), ("hal", 3.9),
        ("P", 4.9), ("R", 5.7), ("F1", 6.5), ("hal", 7.3),
        ("P", 8.1), ("R", 8.9), ("F1", 9.7), ("hal", 10.5),
    ]
    # Better column widths to avoid overlap
    col_xs = [2.9, 3.9, 4.9, 5.7, 6.5, 7.3, 8.1, 8.9, 9.7, 10.5]
    col_w = 1.0
    col_labels = ["cov", "hal", "P", "R", "F1", "hal", "P", "R", "F1", "hal"]
    for x, lbl in zip(col_xs, col_labels):
        add_box(
            ax, x, 5.2, col_w, 0.35, lbl,
            fill="#CFD8DC", fontsize=9, weight="bold",
        )

    # Method column
    for i, m in enumerate(methods):
        y = 4.7 - i * 0.7
        if is_ours[i]:
            method_color = "#1565C0"; weight = "bold"; fill = "#E3F2FD"
        elif is_winner[i]:
            method_color = "#2E7D32"; weight = "bold"; fill = "#E8F5E9"
        else:
            method_color = "#212121"; weight = "normal"; fill = "white"
        add_box(ax, 0.5, y, 2.4, 0.6, m, fill=fill, fontsize=10, weight=weight)
        ax.text(0.5 + 2.3, y + 0.3, "★" if is_ours[i] else ("←best" if is_winner[i] else ""),
                ha="right", va="center", fontsize=9, color=method_color, weight="bold")

        for j, value in enumerate(data[i]):
            cell_color = "white"
            # Highlight F1 columns (5 and 9, 0-indexed: indices 4 and 8 in `value`)
            if j == 4 or j == 7:  # strict_f1 (idx4 in row), deberta_f1 (idx7 in row)
                cell_color = "#FFF9C4"
            add_box(
                ax, col_xs[j], y, col_w, 0.6, f"{value:.2f}",
                fill=cell_color, fontsize=10, weight=weight,
            )

    ax.text(
        6.5, 0.3,
        "★ = our method   |   ←best F1 = winner   |   yellow = F1 columns (headline metric)\n"
        "Loose: all 6 tied at 0.91–0.99 (metric saturated)   "
        "Strict-LLM: B3 best F1=0.49, Ours worst F1=0.28   "
        "DeBERTa: B3 best F1=0.43, Ours worst F1=0.27 (cross-validates strict-LLM)",
        ha="center", va="center", fontsize=8.5, style="italic",
    )

    fig.tight_layout()
    out_path = OUT / "_results_table.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p1 = draw_compare()
    print(f"wrote {p1}")
    p2 = draw_data_flow()
    print(f"wrote {p2}")
    p3 = draw_summary_table()
    print(f"wrote {p3}")


if __name__ == "__main__":
    main()
