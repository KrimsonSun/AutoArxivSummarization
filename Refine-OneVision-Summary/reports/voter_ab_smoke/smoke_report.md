# Voter A/B smoke report

- n_papers: 5
- timestamp: 2026-05-07T20:04:31

## Winner aggregate

| method | agent_qwen | agent_llama | agent_deepseek |
|---|---:|---:|---:|
| claim_grounding | 5 | 0 | 0 |
| borda | 5 | 0 | 0 |

## 2004.04906

### claim_grounding
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=97384, completion=6706, calls=12
  - wall: 189.3s
  - issues raised/addressed: 5/5
  - per-draft scoring:
    D1 (agent_qwen): words=631, total=5, missing=4, density=0.634
    D2 (agent_llama): words=362, total=5, missing=4, density=1.105
    D3 (agent_deepseek): words=430, total=5, missing=4, density=0.930
  - per_label_borda: {'D1': 3.0, 'D3': 2.0, 'D2': 1.0}

### borda
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=107485, completion=8292, calls=18
  - wall: 198.0s
  - issues raised/addressed: 4/4
  - per_label_borda: {'D1': 16.0, 'D2': 6.0, 'D3': 14.0}

## 1706.03762

### claim_grounding
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=49908, completion=6304, calls=10
  - wall: 163.3s
  - issues raised/addressed: 3/3
  - per-draft scoring:
    D1 (agent_qwen): words=636, total=3, missing=2, density=0.314
    D2 (agent_llama): words=336, total=4, missing=4, density=1.190
    D3 (agent_deepseek): words=410, total=3, missing=3, density=0.732
  - per_label_borda: {'D1': 3.0, 'D3': 2.0, 'D2': 1.0}

### borda
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=81960, completion=9360, calls=17
  - wall: 333.7s
  - issues raised/addressed: 3/3
  - per_label_borda: {'D1': 19.0, 'D2': 9.0, 'D3': 14.0}

## 2210.03629

### claim_grounding
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=224248, completion=5966, calls=11
  - wall: 173.1s
  - issues raised/addressed: 4/4
  - per-draft scoring:
    D1 (agent_qwen): words=567, total=4, missing=2, density=0.353
    D2 (agent_llama): words=293, total=3, missing=3, density=1.024
    D3 (agent_deepseek): words=339, total=5, missing=3, density=0.885
  - per_label_borda: {'D1': 3.0, 'D3': 2.0, 'D2': 1.0}

### borda
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=199851, completion=8604, calls=17
  - wall: 339.4s
  - issues raised/addressed: 3/3
  - per_label_borda: {'D1': 18.0, 'D2': 7.0, 'D3': 11.0}

## 2005.11401

### claim_grounding
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=90137, completion=6757, calls=12
  - wall: 199.5s
  - issues raised/addressed: 0/0
  - per-draft scoring:
    D1 (agent_qwen): words=702, total=5, missing=5, density=0.712
    D2 (agent_llama): words=382, total=4, missing=3, density=0.785
    D3 (agent_deepseek): words=407, total=4, missing=4, density=0.983
  - per_label_borda: {'D1': 3.0, 'D2': 2.0, 'D3': 1.0}

### borda
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=109667, completion=9339, calls=18
  - wall: 275.8s
  - issues raised/addressed: 4/4
  - per_label_borda: {'D1': 18.0, 'D2': 6.0, 'D3': 12.0}

## 2308.08155

### claim_grounding
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=84426, completion=6744, calls=11
  - wall: 181.5s
  - issues raised/addressed: 4/4
  - per-draft scoring:
    D1 (agent_qwen): words=662, total=4, missing=4, density=0.604
    D2 (agent_llama): words=411, total=5, missing=5, density=1.217
    D3 (agent_deepseek): words=354, total=4, missing=3, density=0.847
  - per_label_borda: {'D1': 3.0, 'D3': 2.0, 'D2': 1.0}

### borda
  - winner: **agent_qwen** (label D1)
  - tokens: prompt=104664, completion=8632, calls=18
  - wall: 256.7s
  - issues raised/addressed: 4/4
  - per_label_borda: {'D1': 18.0, 'D2': 9.0, 'D3': 15.0}
