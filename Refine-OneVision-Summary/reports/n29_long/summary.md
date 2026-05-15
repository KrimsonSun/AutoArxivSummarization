# OneVision n=29 — config=config/winner_refiner.yaml, method=Ours_onevision_v3_long

- timestamp: 2026-05-08T18:58:29
- attempted: 30, successes: 29, failures: 1
- wall: 47.1 min
- tokens: prompt=3379716, completion=264554

## Winner distribution

- agent_qwen: **7 / 29** (24.1 %)
- agent_llama: **11 / 29** (37.9 %)
- agent_deepseek: **11 / 29** (37.9 %)

## Comparison to PER_PAPER_AUDIT (Borda voter, n=28)

| Voter | Qwen | Llama | DeepSeek |
|---|---|---|---|
| Borda (legacy, original n=29 audit) | **26 / 28 (92.9 %)** | 2 / 28 (7.1 %) | 0 / 28 |
| **claim_grounding (Fix 3)** | 7 / 29 | 11 / 29 | 11 / 29 |

## Failures: 1

- 2106.04561

## Per-paper detail

| arxiv_id | winner | Qwen mi | Llama mi | DS mi |
|---|---|---:|---:|---:|
| 1706.03762 | agent_qwen | 4 | 6 | 5 |
| 1707.06347 | agent_deepseek | 8 | 6 | 5 |
| 1810.04805 | agent_llama | 7 | 6 | 6 |
| 2001.08361 | agent_qwen | - | - | - |
| 2004.04906 | agent_llama | 8 | 6 | 8 |
| 2005.11401 | agent_llama | 8 | 6 | 8 |
| 2005.14165 | agent_llama | 8 | 6 | 6 |
| 2006.11239 | agent_deepseek | 6 | 6 | 5 |
| 2010.11929 | agent_llama | 7 | 6 | 8 |
| 2103.00020 | agent_llama | 10 | 8 | 8 |
| 2104.08691 | agent_deepseek | 8 | 7 | 6 |
| 2106.04561 | ERROR | - | - | - |
| 2106.09685 | agent_deepseek | 5 | 4 | 3 |
| 2112.10752 | agent_qwen | 4 | 5 | 8 |
| 2201.11903 | agent_llama | 6 | 5 | 5 |
| 2203.02155 | agent_deepseek | 8 | 6 | 5 |
| 2203.15556 | agent_deepseek | 8 | 8 | 6 |
| 2204.02311 | agent_qwen | 8 | 8 | 8 |
| 2204.05862 | agent_deepseek | 8 | 8 | 5 |
| 2204.06125 | agent_qwen | 4 | 8 | 6 |
| 2205.14135 | agent_qwen | 5 | 5 | 8 |
| 2210.03629 | agent_llama | 8 | 4 | 6 |
| 2304.02643 | agent_llama | 8 | 6 | 6 |
| 2305.10403 | agent_qwen | 5 | 6 | 6 |
| 2305.10601 | agent_llama | 7 | 5 | 6 |
| 2305.14233 | agent_deepseek | 8 | 8 | 6 |
| 2305.18290 | agent_llama | - | - | - |
| 2308.08155 | agent_deepseek | 8 | 8 | 6 |
| 2310.06825 | agent_deepseek | 7 | 7 | 6 |
| 2402.17764 | agent_deepseek | 8 | 8 | 7 |