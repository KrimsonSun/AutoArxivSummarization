# OneVision n=29 (claim_grounding voter, Fix 1+2+3)

- timestamp: 2026-05-07T21:16:17
- attempted: 30, successes: 29, failures: 1
- wall: 5.1 min
- tokens: prompt=2575863, completion=174538

## Winner distribution

- agent_qwen: **6 / 29** (20.7 %)
- agent_llama: **14 / 29** (48.3 %)
- agent_deepseek: **9 / 29** (31.0 %)

## Comparison to PER_PAPER_AUDIT (Borda voter, n=28)

| Voter | Qwen | Llama | DeepSeek |
|---|---|---|---|
| Borda (legacy, original n=29 audit) | **26 / 28 (92.9 %)** | 2 / 28 (7.1 %) | 0 / 28 |
| **claim_grounding (Fix 3)** | 6 / 29 | 14 / 29 | 9 / 29 |

## Failures: 1

- 2106.04561

## Per-paper detail

| arxiv_id | winner | Qwen mi | Llama mi | DS mi |
|---|---|---:|---:|---:|
| 1706.03762 | agent_qwen | 2 | 3 | 3 |
| 1707.06347 | agent_qwen | 3 | 3 | 3 |
| 1810.04805 | agent_llama | 2 | 0 | 2 |
| 2001.08361 | agent_llama | 3 | 2 | 2 |
| 2004.04906 | agent_llama | 5 | 3 | 4 |
| 2005.11401 | agent_llama | 4 | 3 | 3 |
| 2005.14165 | agent_deepseek | 4 | 3 | 3 |
| 2006.11239 | agent_llama | 3 | 2 | 3 |
| 2010.11929 | agent_qwen | 3 | 3 | 3 |
| 2103.00020 | agent_llama | 8 | 3 | 5 |
| 2104.08691 | agent_qwen | 0 | 3 | 2 |
| 2106.04561 | ERROR | - | - | - |
| 2106.09685 | agent_llama | 3 | 2 | 3 |
| 2112.10752 | agent_llama | 3 | 2 | 2 |
| 2201.11903 | agent_llama | 3 | 3 | 3 |
| 2203.02155 | agent_deepseek | 5 | 5 | 4 |
| 2203.15556 | agent_deepseek | 5 | 4 | 2 |
| 2204.02311 | agent_llama | 3 | 2 | 4 |
| 2204.05862 | agent_llama | 2 | 2 | 3 |
| 2204.06125 | agent_deepseek | 3 | 5 | 3 |
| 2205.14135 | agent_llama | 2 | 2 | 3 |
| 2210.03629 | agent_deepseek | 3 | 3 | 2 |
| 2304.02643 | agent_deepseek | 4 | 3 | 2 |
| 2305.10403 | agent_deepseek | 4 | 4 | 4 |
| 2305.10601 | agent_llama | 3 | 2 | 3 |
| 2305.14233 | agent_qwen | 2 | 3 | 3 |
| 2305.18290 | agent_llama | 4 | 2 | 5 |
| 2308.08155 | agent_deepseek | 4 | 5 | 3 |
| 2310.06825 | agent_deepseek | 3 | 4 | 3 |
| 2402.17764 | agent_qwen | 4 | 5 | 4 |