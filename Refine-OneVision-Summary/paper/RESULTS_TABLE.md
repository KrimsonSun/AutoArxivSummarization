# OneVision n=29 Results — Headline Table

> Standalone summary you can scan in 30 seconds. Full numbers live in
> `Refine-OneVision-Summary/paper/main.tex` Tables 1–3 and the JSON
> at `Evaluation/outputs/experiment/onevision_summary.json`.

## Per-method means (n varies per cell, drops on long papers)

### Strict-LLM judge

| Method                   | n  | F1    | F0.5  | F2    | P     | R     | hal   | mean words |
|:-------------------------|---:|------:|------:|------:|------:|------:|------:|-----------:|
| **Ours_onevision** (this work) | 26 | 0.584 | 0.751 | 0.485 | 0.960 | 0.438 | 0.026 | 702 |
| B1 Llama-70B-naive       | 24 | 0.503 | 0.677 | 0.408 | 0.954 | 0.363 | 0.034 | 525 |
| **B2 Qwen-72B-naive**    | 24 | **0.645** | **0.780** | **0.560** | 0.965 | **0.517** | **0.015** | 726 |
| B3 DeepSeek-V3-naive     | 24 | 0.619 | 0.764 | 0.528 | 0.943 | 0.483 | 0.044 | 514 |
| B4 Llama-8B-naive        | 26 | 0.457 | 0.644 | 0.358 | 0.959 | 0.314 | 0.026 | 450 |
| B5 Llama-70B-structured  | 26 | 0.431 | 0.604 | 0.340 | 0.903 | 0.300 | 0.056 | 504 |
| B6 Llama-70B-v2-prompt   | 25 | 0.478 | 0.655 | 0.380 | 0.906 | 0.336 | 0.062 | 503 |

### DeBERTa-NLI judge

| Method                   | n  | F1    | F0.5  | F2    | P     | R     | hal   | mean words |
|:-------------------------|---:|------:|------:|------:|------:|------:|------:|-----------:|
| **Ours_onevision**       | 27 | 0.515 | 0.595 | 0.466 | 0.684 | 0.445 | **0.252** | 704 |
| B1 Llama-70B-naive       | 23 | 0.431 | 0.529 | 0.374 | 0.661 | 0.349 | 0.289 | 507 |
| **B2 Qwen-72B-naive**    | 26 | **0.559** | **0.598** | **0.533** | 0.642 | **0.520** | 0.307 | 720 |
| B3 DeepSeek-V3-naive     | 27 | 0.506 | 0.546 | 0.489 | 0.596 | 0.489 | 0.353 | 521 |
| B4 Llama-8B-naive        | 25 | 0.407 | 0.517 | 0.345 | 0.681 | 0.316 | 0.276 | 443 |
| B5 Llama-70B-structured  | 26 | 0.383 | 0.493 | 0.323 | 0.647 | 0.295 | 0.308 | 499 |
| B6 Llama-70B-v2-prompt   | 26 | 0.389 | 0.474 | 0.342 | 0.592 | 0.321 | 0.368 | 499 |

## Paired contrasts: ΔF1 (Ours_onevision − baseline), 95 % bootstrap CI

| Baseline                     | Strict ΔF1 | Strict CI | sig | DeBERTa ΔF1 | DeBERTa CI | sig |
|:-----------------------------|-----------:|:----------|:---:|------------:|:-----------|:---:|
| B1 Llama-70B-naive           | +0.078 | [+0.010, +0.142] | ★★ | +0.079 | [+0.034, +0.127] | ★★ |
| **B2 Qwen-72B-naive**        | −0.072 | [−0.136, +0.004] | ns† | −0.044 | [−0.090, +0.007] | ns† |
| B3 DeepSeek-V3-naive         | −0.041 | [−0.114, +0.034] | ns | +0.009 | [−0.049, +0.066] | ns |
| B4 Llama-8B-naive            | +0.128 | [+0.070, +0.185] | ★★ | +0.106 | [+0.062, +0.151] | ★★ |
| B5 Llama-70B-structured      | +0.153 | [+0.103, +0.205] | ★★ | +0.131 | [+0.092, +0.172] | ★★ |
| **B6 Llama-70B-v2-prompt** ★ | **+0.106** | **[+0.047, +0.175]** | **★★** | **+0.126** | **[+0.072, +0.187]** | **★★** |

★ B6 is the architecture-vs.-prompt control: same Llama-70B backbone, same union-bias prompt directives as Ours_onevision's drafters, but a single LLM call with no debate. The +0.106 / +0.126 F1 gap (significant under both decoupled judges) is what isolates the architectural contribution.

★★ = 95 % CI excludes 0 (statistically significant).
ns = 95 % CI crosses 0 (not significant).
† Strict / DeBERTa CIs against B2 Qwen just touch zero from below; we cannot reject the null that OneVision loses to Qwen-72B-naive at this sample size.

## Decomposition: precision vs recall (n=29)

| Contrast               | Strict ΔP | Strict ΔR | DeBERTa ΔP | DeBERTa ΔR |
|:-----------------------|----------:|----------:|-----------:|-----------:|
| Ours_onevision − B6    | +0.054    | **+0.101** | +0.092    | **+0.126** |
| Ours_onevision − B1    | +0.006    | **+0.072** | +0.023    | **+0.097** |
| Ours_onevision − B2    | −0.005    | −0.089    | +0.042    | −0.073     |

The recall component dominates the within-family gain (vs B6, B1). The B2 gap is also a recall gap — Qwen retrieves more paper specifics per call than OneVision does after voting.

## Side-by-side: n=15 vs n=29

| Contrast | n=15 strict | **n=29 strict** | n=15 deberta | **n=29 deberta** |
|:---------|------------:|----------------:|-------------:|-----------------:|
| OneVision − B1 | +0.140 ★★ | **+0.078 ★★** | +0.101 ★★ | +0.079 ★★ |
| OneVision − **B2** | −0.033 ns | **−0.072 ns† (CI touches 0)** | −0.037 ns | −0.044 ns† |
| OneVision − **B3** | +0.056 ns | **−0.041 ns (sign flip)** | +0.073 ns | +0.009 ns |
| OneVision − B4 | +0.200 ★★ | +0.128 ★★ | +0.132 ★★ | +0.106 ★★ |
| OneVision − B5 | +0.197 ★★ | +0.153 ★★ | +0.126 ★★ | +0.131 ★★ |
| **OneVision − B6** | **+0.153 ★★** | **+0.106 ★★** | **+0.150 ★★** | **+0.126 ★★** |

Going n=15 → n=29 the architectural-control contrast (vs B6) **shrunk by ~30 %** but stayed significant under both judges. The DeepSeek contrast flipped sign (B3 vs OneVision now favours DeepSeek by 0.04 strict, n.s.). The B2 Qwen gap widened.

## One-sentence takeaway

> **At n=29, the OneVision pipeline still significantly beats a same-prompt single-LLM control (B6) by +0.10–+0.13 F1 under both decoupled judges, but ties or slightly loses to the strongest cross-family single-LLM baselines (Qwen-72B-naive, DeepSeek-V3-naive). The architectural contribution is real within-family but does not lift Llama-70B above Qwen-72B-naive on this task.**
