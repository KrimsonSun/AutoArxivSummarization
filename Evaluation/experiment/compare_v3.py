"""OneVision v3 (post-Fix-1+2+3 voter) vs baselines + vs OneVision v1.

Reads:
  outputs/experiment/evals_strict/<id>/{Ours_onevision_v3, B1..B6}.eval.json
  outputs/experiment/evals_deberta/<id>/{Ours_onevision_v3, B1..B6}.eval.json
  (optionally Ours_onevision_v3 vs the old Ours_onevision if v1 evals exist)

Reports per evaluator:
  - Per-method mean F1 / F0.5 / F2 / P / R / hallucination / words
  - Paired bootstrap (10 000 resamples) CI on (Ours_v3 − baseline) for B1-B6
  - Cohen's d, W/L/T per paper
  - If Ours_onevision (v1) evals exist, also report Ours_v3 vs v1 paired diff

Writes outputs/experiment/v3_summary.json + v3_summary.md.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np

EVAL_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "experiment"

PRIMARY = "Ours_onevision_v3"
WINNER_REFINER = "Ours_onevision_v3_w"  # winner_refiner config (use_winner_as_refiner=True)
LEGACY_V1 = "Ours_onevision"  # only included if its evals exist
BASELINES = [
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
    return d


def boot_ci(diffs: list[float], iters: int = 10_000, seed: int = 42) -> tuple[float, float, float]:
    arr = np.array(diffs)
    rng = np.random.default_rng(seed)
    boot = np.empty(iters)
    n = len(arr)
    for i in range(iters):
        boot[i] = arr[rng.integers(0, n, size=n)].mean()
    return float(arr.mean()), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def cohens_d(diffs: list[float]) -> float:
    if len(diffs) < 2:
        return 0.0
    mu = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    return mu / sd if sd > 0 else 0.0


def measure_length(paper_id: str, method: str) -> int | None:
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
        text: list[str] = []
        for k in ("tldr", "core_idea"):
            v = d.get(k)
            if isinstance(v, str):
                text.append(v)
        for c in d.get("key_contributions") or []:
            if isinstance(c, dict):
                text.append(c.get("text", ""))
        m = d.get("method") or {}
        text.append(m.get("overview", "") or "")
        for comp in m.get("components") or []:
            text.append((comp.get("name", "") + " " + comp.get("description", "")) if isinstance(comp, dict) else "")
        e = d.get("experiments") or {}
        text.append(e.get("setup", "") or "")
        for f in e.get("key_findings") or []:
            if isinstance(f, dict):
                text.append(f.get("text", ""))
        for lim in d.get("limitations") or []:
            if isinstance(lim, str):
                text.append(lim)
        return sum(len(t.split()) for t in text)
    return None


def per_method_summary(eval_dir: str, papers: list[str], methods: list[str]) -> dict:
    out: dict[str, dict] = {}
    for m in methods:
        f1s, fhs, fts, ps, rs, hs, words = [], [], [], [], [], [], []
        for pid in papers:
            cell = load_eval(eval_dir, pid, m)
            if cell is None:
                continue
            f1s.append(cell["f1"])
            fhs.append(cell.get("f_half", cell.get("f0_5", 0.0)))
            fts.append(cell.get("f_two", cell.get("f2", 0.0)))
            ps.append(cell["evidence_coverage"])
            rs.append(cell["paper_recall"])
            hs.append(cell["hallucination_rate"])
            w = measure_length(pid, m)
            if w is not None:
                words.append(w)
        out[m] = {
            "n": len(f1s),
            "mean_f1": statistics.mean(f1s) if f1s else None,
            "std_f1": statistics.stdev(f1s) if len(f1s) > 1 else None,
            "mean_f_half": statistics.mean(fhs) if fhs else None,
            "mean_f_two": statistics.mean(fts) if fts else None,
            "mean_p": statistics.mean(ps) if ps else None,
            "mean_r": statistics.mean(rs) if rs else None,
            "mean_hal": statistics.mean(hs) if hs else None,
            "mean_words": statistics.mean(words) if words else None,
        }
    return out


def paired_diffs(eval_dir: str, papers: list[str], a: str, b: str) -> dict:
    diffs_f1, diffs_p, diffs_r = [], [], []
    a_f1, b_f1 = [], []
    wins = losses = ties = 0
    n_paired_papers = 0
    for pid in papers:
        ca = load_eval(eval_dir, pid, a)
        cb = load_eval(eval_dir, pid, b)
        if ca is None or cb is None:
            continue
        n_paired_papers += 1
        d = ca["f1"] - cb["f1"]
        diffs_f1.append(d)
        diffs_p.append(ca["evidence_coverage"] - cb["evidence_coverage"])
        diffs_r.append(ca["paper_recall"] - cb["paper_recall"])
        a_f1.append(ca["f1"])
        b_f1.append(cb["f1"])
        if d > 0.005: wins += 1
        elif d < -0.005: losses += 1
        else: ties += 1
    if not diffs_f1:
        return {"n": 0}
    mean, lo, hi = boot_ci(diffs_f1)
    return {
        "n": n_paired_papers,
        "mean_diff_f1": mean,
        "ci95_low": lo,
        "ci95_high": hi,
        "cohens_d": cohens_d(diffs_f1),
        "mean_diff_p": statistics.mean(diffs_p),
        "mean_diff_r": statistics.mean(diffs_r),
        "wins": wins, "losses": losses, "ties": ties,
        "mean_a_f1": statistics.mean(a_f1),
        "mean_b_f1": statistics.mean(b_f1),
        "significant": (lo > 0) or (hi < 0),
    }


def render_judge_section(label: str, eval_dir: str, papers: list[str]) -> tuple[dict, list[str]]:
    methods = [PRIMARY]
    has_winner_refiner = any(load_eval(eval_dir, pid, WINNER_REFINER) is not None for pid in papers)
    if has_winner_refiner:
        methods.append(WINNER_REFINER)
    methods.extend(BASELINES)
    if any(load_eval(eval_dir, pid, LEGACY_V1) is not None for pid in papers):
        methods.insert(2 if has_winner_refiner else 1, LEGACY_V1)
    per_method = per_method_summary(eval_dir, papers, methods)

    lines: list[str] = []
    lines.append(f"## {label}")
    lines.append("")
    lines.append("### Per-method means")
    lines.append("")
    lines.append("| Method | n | F1 | F0.5 | F2 | P | R | hal | words |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in methods:
        s = per_method[m]
        if s["mean_f1"] is None:
            continue
        if m == PRIMARY:
            marker = " ⭐"
        elif m == WINNER_REFINER:
            marker = " ⭐⭐"
        else:
            marker = ""
        lines.append(
            f"| {m}{marker} | {s['n']} | "
            f"{s['mean_f1']:.3f} | {s['mean_f_half']:.3f} | {s['mean_f_two']:.3f} | "
            f"{s['mean_p']:.3f} | {s['mean_r']:.3f} | {s['mean_hal']:.3f} | "
            f"{s['mean_words']:.0f} |"
        )
    lines.append("")
    lines.append("### Paired contrasts ΔF1 = Ours_v3 − baseline (10 000-resample bootstrap)")
    lines.append("")
    lines.append("| Baseline | n_paired | mean ΔF1 | 95 % CI | Cohen's d | ΔP | ΔR | W / L / T | sig |")
    lines.append("|---|---:|---:|---|---:|---:|---:|---|:---:|")
    paired: dict[str, dict] = {}
    for b in BASELINES:
        d = paired_diffs(eval_dir, papers, PRIMARY, b)
        paired[b] = d
        if d["n"] == 0:
            lines.append(f"| {b} | 0 | - | - | - | - | - | - | - |")
            continue
        sig = "**★★**" if d["significant"] else "ns"
        lines.append(
            f"| {b} | {d['n']} | {d['mean_diff_f1']:+.3f} | "
            f"[{d['ci95_low']:+.3f}, {d['ci95_high']:+.3f}] | "
            f"{d['cohens_d']:+.2f} | {d['mean_diff_p']:+.3f} | {d['mean_diff_r']:+.3f} | "
            f"{d['wins']} / {d['losses']} / {d['ties']} | {sig} |"
        )
    lines.append("")
    if has_winner_refiner:
        # Direct comparison: v3 (static Llama refiner) vs v3_w (winner-as-refiner)
        d = paired_diffs(eval_dir, papers, WINNER_REFINER, PRIMARY)
        if d["n"]:
            lines.append("### Direct contrast: v3_w vs v3 (use_winner_as_refiner: True − False)")
            lines.append("")
            sig = "**★★**" if d["significant"] else "ns"
            lines.append(f"- n_paired = {d['n']}")
            lines.append(f"- ΔF1 (v3_w − v3) = **{d['mean_diff_f1']:+.3f}**, 95 % CI [{d['ci95_low']:+.3f}, {d['ci95_high']:+.3f}], d = {d['cohens_d']:+.2f}, {sig}")
            lines.append(f"- ΔP = {d['mean_diff_p']:+.3f}, ΔR = {d['mean_diff_r']:+.3f}")
            lines.append(f"- v3_w wins / losses / ties: {d['wins']} / {d['losses']} / {d['ties']}")
            lines.append("")

        # v3_w vs each baseline
        lines.append("### Paired contrasts ΔF1 = Ours_v3_w − baseline (10 000-resample bootstrap)")
        lines.append("")
        lines.append("| Baseline | n_paired | mean ΔF1 | 95 % CI | Cohen's d | ΔP | ΔR | W / L / T | sig |")
        lines.append("|---|---:|---:|---|---:|---:|---:|---|:---:|")
        for b in BASELINES:
            d = paired_diffs(eval_dir, papers, WINNER_REFINER, b)
            if d["n"] == 0:
                lines.append(f"| {b} | 0 | - | - | - | - | - | - | - |")
                continue
            sig = "**★★**" if d["significant"] else "ns"
            lines.append(
                f"| {b} | {d['n']} | {d['mean_diff_f1']:+.3f} | "
                f"[{d['ci95_low']:+.3f}, {d['ci95_high']:+.3f}] | "
                f"{d['cohens_d']:+.2f} | {d['mean_diff_p']:+.3f} | {d['mean_diff_r']:+.3f} | "
                f"{d['wins']} / {d['losses']} / {d['ties']} | {sig} |"
            )
        lines.append("")

    if LEGACY_V1 in methods:
        d = paired_diffs(eval_dir, papers, PRIMARY, LEGACY_V1)
        if d["n"]:
            lines.append("### Direct contrast: v3 (new voter) vs v1 (legacy Borda voter)")
            lines.append("")
            sig = "**★★**" if d["significant"] else "ns"
            lines.append(f"- n_paired = {d['n']}")
            lines.append(f"- ΔF1 = **{d['mean_diff_f1']:+.3f}**, 95 % CI [{d['ci95_low']:+.3f}, {d['ci95_high']:+.3f}], d = {d['cohens_d']:+.2f}, {sig}")
            lines.append(f"- ΔP = {d['mean_diff_p']:+.3f}, ΔR = {d['mean_diff_r']:+.3f}")
            lines.append(f"- v3 wins / losses / ties: {d['wins']} / {d['losses']} / {d['ties']}")
            lines.append("")
    return {"per_method": per_method, "paired_v3_vs_baseline": paired}, lines


def main() -> None:
    # Discover papers from the strict eval dir.
    strict_dir = EVAL_ROOT / "evals_strict"
    deberta_dir = EVAL_ROOT / "evals_deberta"
    sources = []
    if strict_dir.exists():
        sources.append(("Strict-LLM judge", "evals_strict"))
    if deberta_dir.exists():
        sources.append(("DeBERTa-NLI judge", "evals_deberta"))
    if not sources:
        print("No eval dirs found under outputs/experiment/. Run strict_reeval first.")
        return

    papers = sorted({
        p.name
        for src in sources
        for p in (EVAL_ROOT / src[1]).iterdir()
        if p.is_dir()
    })
    print(f"Reporting on {len(papers)} papers across {[s[0] for s in sources]}")

    md_lines = ["# OneVision v3 evaluation report (n=29)"]
    md_lines.append("")
    md_lines.append(f"- methods: {PRIMARY} (primary) + 6 baselines (B1-B6) + (optional) {LEGACY_V1} legacy")
    md_lines.append(f"- judges: {' + '.join(s[0] for s in sources)}")
    md_lines.append(f"- bootstrap: 10 000 resamples, paired by paper, seed=42")
    md_lines.append("")

    full: dict = {"papers": papers, "judges": {}}
    for label, eval_dir in sources:
        section, section_lines = render_judge_section(label, eval_dir, papers)
        full["judges"][eval_dir] = section
        md_lines.extend(section_lines)

    out_md = EVAL_ROOT / "v3_summary.md"
    out_json = EVAL_ROOT / "v3_summary.json"
    out_md.write_text("\n".join(md_lines))
    out_json.write_text(json.dumps(full, indent=2, default=str))
    print(f"\nwrote {out_md}")
    print(f"wrote {out_json}")
    print()
    # Also print to stdout for live inspection.
    print("\n".join(md_lines))


if __name__ == "__main__":
    main()
