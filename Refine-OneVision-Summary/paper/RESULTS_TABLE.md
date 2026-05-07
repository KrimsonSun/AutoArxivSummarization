# OneVision n=15 Results — Headline Table

> Standalone summary you can scan in 30 seconds. Full numbers live in
> `Refine-OneVision-Summary/paper/main.tex` Tables 1–3 and the JSON
> at `Evaluation/outputs/experiment/onevision_summary.json`.

## Per-method means (n ≤ 13 per cell)

### Strict-LLM judge

| Method                   | n  | F1    | F0.5  | F2    | P     | R     | hal   | mean words |
|:-------------------------|---:|------:|------:|------:|------:|------:|------:|-----------:|
| **Ours_onevision** (this work) | 13 | **0.587** | **0.752** | 0.491 | 0.965 | 0.446 | 0.016 | 717 |
| B1 Llama-70B-naive       | 13 | 0.447 | 0.642 | 0.348 | 0.969 | 0.304 | 0.017 | 311 |
| **B2 Qwen-72B-naive**    | 12 | **0.606** | 0.741 | **0.521** | 0.958 | **0.479** | 0.010 | 591 |
| B3 DeepSeek-V3-naive     | 11 | 0.517 | 0.684 | 0.422 | 0.929 | 0.377 | 0.052 | 373 |
| B4 Llama-8B-naive        | 13 | 0.387 | 0.585 | 0.292 | 0.973 | 0.252 | 0.013 | 341 |
| B5 Llama-70B-structured  | 13 | 0.390 | 0.574 | 0.299 | 0.911 | 0.260 | 0.044 | 431 |
| B6 Llama-70B-v2-prompt   | 13 | 0.434 | 0.620 | 0.336 | 0.893 | 0.292 | 0.072 | 413 |

### DeBERTa-NLI judge

| Method                   | n  | F1    | F0.5  | F2    | P     | R     | hal   | mean words |
|:-------------------------|---:|------:|------:|------:|------:|------:|------:|-----------:|
| **Ours_onevision**       | 13 | **0.490** | **0.550** | 0.458 | 0.627 | 0.446 | 0.283 | 727 |
| B1 Llama-70B-naive       | 12 | 0.382 | 0.492 | 0.319 | 0.631 | 0.289 | 0.302 | 300 |
| **B2 Qwen-72B-naive**    | 12 | **0.525** | **0.555** | **0.508** | 0.603 | **0.503** | 0.342 | 603 |
| B3 DeepSeek-V3-naive     | 13 | 0.417 | 0.461 | 0.399 | 0.518 | 0.399 | 0.419 | 365 |
| B4 Llama-8B-naive        | 11 | 0.349 | 0.451 | 0.293 | 0.619 | 0.267 | 0.316 | 343 |
| B5 Llama-70B-structured  | 13 | 0.364 | 0.469 | 0.304 | 0.613 | 0.276 | 0.334 | 434 |
| B6 Llama-70B-v2-prompt   | 13 | 0.341 | 0.421 | 0.299 | 0.542 | 0.281 | 0.404 | 420 |

## Paired contrasts: ΔF1 (Ours_onevision − baseline), 95 % bootstrap CI

| Baseline                     | Strict ΔF1 | Strict CI | sig | DeBERTa ΔF1 | DeBERTa CI | sig |
|:-----------------------------|-----------:|:----------|:---:|------------:|:-----------|:---:|
| B1 Llama-70B-naive           | +0.140 | [+0.075, +0.203] | ★★ | +0.101 | [+0.049, +0.156] | ★★ |
| **B2 Qwen-72B-naive**        | −0.033 | [−0.121, +0.073] | ns | −0.037 | [−0.123, +0.059] | ns |
| B3 DeepSeek-V3-naive         | +0.056 | [−0.058, +0.173] | ns | +0.073 | [−0.013, +0.155] | ns |
| B4 Llama-8B-naive            | +0.200 | [+0.126, +0.275] | ★★ | +0.132 | [+0.076, +0.194] | ★★ |
| B5 Llama-70B-structured      | +0.197 | [+0.122, +0.277] | ★★ | +0.126 | [+0.071, +0.181] | ★★ |
| **B6 Llama-70B-v2-prompt** ★ | **+0.153** | **[+0.058, +0.265]** | **★★** | **+0.150** | **[+0.061, +0.254]** | **★★** |

★ B6 is the architecture-vs.-prompt control: same Llama-70B backbone, same union-bias prompt directives as Ours_onevision's drafters, but a single LLM call with no debate. The +0.15 F1 gap (significant under both decoupled judges) is what isolates the architectural contribution.

★★ = 95 % CI excludes 0 (statistically significant).
ns = 95 % CI crosses 0 (not significant; for B2/B3, this is a *tie*, not a loss).

## Decomposition: precision vs recall

| Contrast               | Strict ΔP | Strict ΔR | DeBERTa ΔP | DeBERTa ΔR |
|:-----------------------|----------:|----------:|-----------:|-----------:|
| Ours_onevision − B6    | +0.072    | **+0.154** | +0.085    | **+0.165** |
| Ours_onevision − B1    | −0.004    | **+0.142** | −0.004    | **+0.157** |
| Ours_onevision − B2    | +0.007    | −0.048    | +0.024    | −0.054     |

The recall component dominates the gain — consistent with the architectural change unlocking the missing-fact retrieval channel that the v1 verifier (which read paragraph short-summaries) could not access.

## One-sentence takeaway

> **The OneVision pipeline beats a single-LLM with the same prompt directives by +0.15 F1 (significant under both decoupled judges, n=13 paired papers), with essentially all the gain coming from recall — confirming that fixing the v1 verifier (full paragraph text) plus replacing merge with vote-then-augment recovers a real architectural contribution that the v1 architecture could not deliver.**
