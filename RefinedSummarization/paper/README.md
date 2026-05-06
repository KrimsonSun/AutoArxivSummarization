# Paper draft

LaTeX source for "Multi-Agent Debate Fails on Union-Reconstruction
Tasks: A Negative Result on RAG-Grounded Scientific Summarization".

```
paper/
├── main.tex              ← single-file LaTeX (compiles standalone)
├── references.bib        ← BibTeX (≈21 entries)
├── stats.json            ← raw numbers behind every claim in the paper
├── figures/
│   ├── pipeline_compare.png       (the 3-mode pipeline overview)
│   ├── pipeline_data_flow.png     (per-step data shapes)
│   ├── per_paper_scatter.png      (Ours vs each baseline, all 29 papers)
│   ├── diff_distribution.png      (histogram of F1 diffs vs B2 + bootstrap CI)
│   ├── mean_loose.png             (saturated; included as sanity baseline)
│   ├── mean_strict.png            (strict-LLM means with std-dev error bars)
│   ├── mean_deberta.png           (DeBERTa-NLI means with std-dev error bars)
│   └── results_table.png          (3-mode comparison table)
└── README.md             ← this file
```

## Revision notes (2026-05-05)

The current draft has been revised to address the following issues
flagged in review:

1. **Statistical rigour added** (Section 5):
   - Paired-bootstrap 95% CI on F1 differences for every Ours-vs-baseline
     pair (10k iterations, paired across the same 28 papers).
   - Cohen's $d$ effect sizes.
   - Per-paper W/L/T counts at $\pm 0.02$ tolerance.
   - Two new figures: `per_paper_scatter.png` and `diff_distribution.png`.
2. **Reframed finding**: rather than "Ours loses to all baselines", the
   data shows Ours loses with very-large effect to *out-of-Llama-family*
   baselines (Qwen, DeepSeek), but is statistically tied within the
   Llama-70B family. This is the more interesting and accurate framing.
3. **Mechanism M4 retracted**: B5 (structured-prompt single-LLM) and
   B1 (naive single-LLM) achieve statistically indistinguishable F1
   ($0.405$ vs.\ $0.418$, CI overlap), so the schema-rewards-abstraction
   hypothesis is not supported by the data.
4. **Mechanism M2 evidence added**: verifier returns the cap of 12 issues
   on every paper; refiner self-reports addressing 12 of 12 every paper;
   yet recall stays at $0.24$. Suggests rubber-stamp behaviour.
5. **Mechanism M1 case studies added**: DPR, FlashAttention, Constitutional
   AI — papers where Ours wrote *more* atomic claims than B2 but covered
   *fewer* paper facts, indicating intersection-style merge.
6. **Task taxonomy** introduced: consensus-reasoning vs.\ union-reconstruction.
   Multi-agent debate is task-type-conditional.
7. **SpecEM contrast** added in Related Work to support the taxonomy.
8. **Reproducibility section** adds OpenRouter snapshot model IDs,
   exact temperatures, max_tokens, paper-claim-cache constancy, total
   cost, single-seed disclosure with within-experiment std-dev as proxy.
9. **iLLMV citation** now explicitly flagged as PLACEHOLDER in the
   `references.bib` to prevent accidental submission with anonymous author.

## Compile locally

```bash
cd paper/
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Upload to Overleaf

Easiest path:

1. Go to https://www.overleaf.com/project/new/upload
2. Drag-drop the entire `paper/` directory as a `.zip`, OR
3. Create a new "Blank Project", then upload `main.tex`, `references.bib`,
   and the contents of `figures/`. Set `main.tex` as the main document.

Compiler: **pdfLaTeX**.

## Switching to a conference template

The current `\documentclass{article}` makes the file portable. To
target ACL 2024 / EMNLP / NeurIPS:

| Template | Replace top of `main.tex` with |
|---|---|
| ACL 2024 | `\documentclass[11pt]{article}\usepackage[review]{acl}\usepackage{times}` |
| NeurIPS 2024 | `\documentclass{article}\usepackage[final]{neurips_2024}` |
| ICLR 2025 | `\documentclass{article}\usepackage{iclr2025_conference}` |

Then upload the corresponding `acl.sty` / `neurips_2024.sty` /
`iclr2025_conference.sty` from the conference's official template
package alongside `main.tex`.

## Re-generating figures

The figures are produced by:

```bash
cd ../../Evaluation
.venv/bin/python -m experiment.plot --mode loose
.venv/bin/python -m experiment.plot --mode strict
.venv/bin/python -m experiment.plot --mode deberta
.venv/bin/python -m experiment.draw_diagrams
```

After regeneration, copy them back to `paper/figures/`:

```bash
cp ../Evaluation/outputs/experiment/plots/_mean.png         figures/mean_loose.png
cp ../Evaluation/outputs/experiment/plots_strict/_mean.png  figures/mean_strict.png
cp ../Evaluation/outputs/experiment/plots_deberta/_mean.png figures/mean_deberta.png
cp ../Evaluation/outputs/experiment/plots/_pipeline_compare.png figures/pipeline_compare.png
cp ../Evaluation/outputs/experiment/plots/_pipeline_data_flow.png figures/pipeline_data_flow.png
cp ../Evaluation/outputs/experiment/plots/_results_table.png figures/results_table.png
```

## Caveats

- The `iLLMV (BigData 2025)` reference is anonymised in `references.bib`
  pending publication; replace with the real citation when available.
- Numbers in the `results_table.png` and the abstract correspond to
  the n=29 (seed=42) experiment. If you re-run with different `n` or
  `seed`, regenerate `_results_table.png` via `experiment.draw_diagrams`
  and re-copy.
