# OneVision n=29 — config=config/winner_refiner.yaml, method=Ours_onevision_v3_w

- timestamp: 2026-05-08T12:45:11
- attempted: 30, successes: 29, failures: 1
- wall: 18.2 min
- tokens: prompt=2368447, completion=149087

## Winner distribution

- agent_qwen: **8 / 29** (27.6 %)
- agent_llama: **19 / 29** (65.5 %)
- agent_deepseek: **2 / 29** (6.9 %)

## Comparison to PER_PAPER_AUDIT (Borda voter, n=28)

| Voter | Qwen | Llama | DeepSeek |
|---|---|---|---|
| Borda (legacy, original n=29 audit) | **26 / 28 (92.9 %)** | 2 / 28 (7.1 %) | 0 / 28 |
| **claim_grounding (Fix 3)** | 8 / 29 | 19 / 29 | 2 / 29 |

## Failures: 1

- 2106.04561

## Per-paper detail

| arxiv_id | winner | Qwen mi | Llama mi | DS mi |
|---|---|---:|---:|---:|
| 1706.03762 | agent_deepseek | 3 | 3 | 2 |
| 1707.06347 | agent_llama | - | - | - |
| 1810.04805 | agent_llama | - | - | - |
| 2001.08361 | agent_qwen | - | - | - |
| 2004.04906 | agent_qwen | 3 | 4 | 5 |
| 2005.11401 | agent_llama | - | - | - |
| 2005.14165 | agent_llama | 3 | 3 | 3 |
| 2006.11239 | agent_llama | - | - | - |
| 2010.11929 | agent_llama | - | - | - |
| 2103.00020 | agent_llama | - | - | - |
| 2104.08691 | agent_qwen | 3 | 3 | 3 |
| 2106.04561 | ERROR | - | - | - |
| 2106.09685 | agent_qwen | 3 | 3 | 3 |
| 2112.10752 | agent_llama | - | - | - |
| 2201.11903 | agent_qwen | 3 | 3 | 3 |
| 2203.02155 | agent_llama | - | - | - |
| 2203.15556 | agent_llama | 3 | 3 | 3 |
| 2204.02311 | agent_qwen | 3 | 4 | 4 |
| 2204.05862 | agent_llama | - | - | - |
| 2204.06125 | agent_deepseek | 4 | 4 | 2 |
| 2205.14135 | agent_llama | - | - | - |
| 2210.03629 | agent_llama | 2 | 1 | 2 |
| 2304.02643 | agent_qwen | 2 | 2 | 3 |
| 2305.10403 | agent_llama | - | - | - |
| 2305.10601 | agent_llama | - | - | - |
| 2305.14233 | agent_qwen | 2 | 3 | 3 |
| 2305.18290 | agent_llama | 4 | 3 | 3 |
| 2308.08155 | agent_llama | - | - | - |
| 2310.06825 | agent_llama | 3 | 2 | 4 |
| 2402.17764 | agent_llama | 4 | 3 | 3 |