# OneVision n=29 — config=config/iterative.yaml, method=Ours_onevision_v3_iter

- timestamp: 2026-05-11T18:01:17
- attempted: 30, successes: 28, failures: 2
- wall: 44.7 min
- tokens: prompt=6565943, completion=396484

## Winner distribution

- agent_qwen: **10 / 28** (35.7 %)
- agent_llama: **16 / 28** (57.1 %)
- agent_deepseek: **2 / 28** (7.1 %)

## Comparison to PER_PAPER_AUDIT (Borda voter, n=28)

| Voter | Qwen | Llama | DeepSeek |
|---|---|---|---|
| Borda (legacy, original n=29 audit) | **26 / 28 (92.9 %)** | 2 / 28 (7.1 %) | 0 / 28 |
| **claim_grounding (Fix 3)** | 10 / 28 | 16 / 28 | 2 / 28 |

## Failures: 2

- 2001.08361
- 2106.04561

## Per-paper detail

| arxiv_id | winner | Qwen mi | Llama mi | DS mi |
|---|---|---:|---:|---:|
| 1706.03762 | agent_llama | - | - | - |
| 1707.06347 | agent_qwen | 5 | 6 | 6 |
| 1810.04805 | agent_qwen | 5 | 6 | 5 |
| 2001.08361 | ERROR | - | - | - |
| 2004.04906 | agent_llama | - | - | - |
| 2005.11401 | agent_qwen | 5 | 8 | 8 |
| 2005.14165 | agent_llama | 8 | 5 | 8 |
| 2006.11239 | agent_llama | 5 | 4 | 5 |
| 2010.11929 | agent_qwen | 6 | 6 | 6 |
| 2103.00020 | agent_llama | 8 | 5 | 8 |
| 2104.08691 | agent_llama | 8 | 5 | 10 |
| 2106.04561 | ERROR | - | - | - |
| 2106.09685 | agent_llama | 5 | 4 | 5 |
| 2112.10752 | agent_llama | 4 | 3 | 5 |
| 2201.11903 | agent_qwen | 5 | 5 | 6 |
| 2203.02155 | agent_deepseek | 8 | 8 | 4 |
| 2203.15556 | agent_qwen | 8 | 8 | 8 |
| 2204.02311 | agent_deepseek | 8 | 8 | 5 |
| 2204.05862 | agent_llama | 8 | 6 | 6 |
| 2204.06125 | agent_llama | 6 | 4 | 6 |
| 2205.14135 | agent_llama | - | - | - |
| 2210.03629 | agent_qwen | - | - | - |
| 2304.02643 | agent_llama | 4 | 3 | 5 |
| 2305.10403 | agent_llama | 8 | 6 | 7 |
| 2305.10601 | agent_qwen | 6 | 8 | 8 |
| 2305.14233 | agent_qwen | - | - | - |
| 2305.18290 | agent_llama | 5 | 4 | 4 |
| 2308.08155 | agent_llama | 8 | 4 | 8 |
| 2310.06825 | agent_qwen | 5 | 8 | 6 |
| 2402.17764 | agent_llama | 5 | 4 | 5 |