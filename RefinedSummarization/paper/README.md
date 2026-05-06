# Paper draft

LaTeX source for "When Multi-Agent Debate Hurts Coverage: A Negative
Result on RAG-Grounded Scientific Summarization".

```
paper/
├── main.tex              ← single-file LaTeX (compiles standalone)
├── references.bib        ← BibTeX (≈18 entries)
├── figures/
│   ├── pipeline_compare.png
│   ├── pipeline_data_flow.png
│   ├── results_table.png
│   ├── mean_loose.png
│   ├── mean_strict.png
│   └── mean_deberta.png
└── README.md             ← this file
```

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
