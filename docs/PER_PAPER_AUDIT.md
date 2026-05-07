# Per-paper outcome audit (n=29 OneVision experiment)

Audit table produced 2026-05-07 from `outputs/experiment/`. Documents
which agent won the OneVision Stage-2 vote per paper, alongside each
method's strict-LLM F1, the strongest baseline per paper, and whether
OneVision (best of v1 / v2) actually beat it. Source artefact for
Lesson L9.

This file is a **frozen snapshot**. To regenerate, see EXPERIMENTS
E15 / E24.

---

## Voter-winner aggregate

| Voter winner | Frequency |
|---|---:|
| **agent_qwen** | 26 / 28 (92.9 %) |
| agent_llama | 2 / 28 (7.1 %) |
| agent_deepseek | 0 / 28 (0 %) |

Borda margin median = 8.0 (Borda total range 9–27); Qwen typically
wins by a clear 24 / 16 / 8 spread.

## Per-paper full table (strict-LLM F1)

```
paper        win     |  OV_v1  OV_v2 |  B1_Lla  B2_Qwn  B3_DSk  B6_Lv2 | best      OV>best?
----------------------------------------------------------------------------------------------------
2204.06125   Qwen    |  0.635    -   |   0.348   0.676   0.555   0.629 | B2  0.676     -0.040
2104.08691   Qwen    |  0.761  0.816 |   0.626     -     0.560   0.350 | B1  0.626     +0.190
1706.03762   Qwen    |  0.846  0.734 |   0.545   0.824   0.429   0.548 | B2  0.824     +0.022
2112.10752   Llama   |  0.710  0.788 |   0.596   0.811   0.688   0.457 | B2  0.811     -0.023
2204.02311   Qwen    |  0.553  0.595 |   0.545   0.604   0.427   0.513 | B2  0.604        tie
2305.10403   Qwen    |  0.584  0.802 |   0.621   0.607   0.791   0.471 | B3  0.791        tie
1707.06347   Qwen    |    -    0.659 |   0.431   0.542     -       -   | B2  0.542     +0.117
2106.09685   Qwen    |  0.430  0.427 |   0.396   0.610   0.560   0.433 | B2  0.610     -0.180
2106.04561   ?       |    -      -   |   0.571   0.596     -     0.644 | B6  0.644          -
2308.08155   Qwen    |  0.914  0.889 |   0.662   0.974     -     0.257 | B2  0.974     -0.060
2005.14165   Qwen    |  0.512  0.541 |   0.328   0.474   0.394   0.462 | B2  0.474     +0.068
2010.11929   Qwen    |  0.410    -   |   0.391   0.712     -     0.434 | B2  0.712     -0.302
2204.05862   Qwen    |  0.330    -   |   0.298   0.481   0.498   0.341 | B3  0.498     -0.168
1810.04805   Qwen    |  0.458  0.601 |   0.280   0.447   0.605   0.417 | B3  0.605        tie
2004.04906   Qwen    |  0.491  0.426 |   0.182   0.049   0.182   0.330 | B6  0.330     +0.161
2305.10601   Qwen    |  0.667  0.569 |   0.594     -     0.611   0.473 | B3  0.611     +0.056
2304.02643   Qwen    |  0.655  0.505 |   0.462   0.316   0.730   0.644 | B3  0.730     -0.075
2205.14135   Qwen    |  0.667  0.838 |   0.788   0.912   0.933   0.589 | B3  0.933     -0.095
2305.14233   Llama   |  0.491    -   |   0.655   0.696   0.825   0.692 | B3  0.825     -0.334
2203.15556   Qwen    |  0.304    -   |   0.537   0.621   0.469   0.286 | B2  0.621     -0.317
2210.03629   Qwen    |  0.667  0.474 |     -     0.788   0.669   0.498 | B2  0.788     -0.121
2203.02155   Qwen    |  0.431    -   |   0.117   0.617   0.644   0.391 | B3  0.644     -0.213
2305.18290   Qwen    |  0.730  0.788 |   0.674   0.632   0.728   0.691 | B3  0.728     +0.059
2310.06825   Qwen    |  0.788    -   |   0.769   0.947   0.849   0.659 | B2  0.947     -0.159
2402.17764   Qwen    |  0.598    -   |   0.697   0.796   0.653     -   | B2  0.796     -0.198
2006.11239   Qwen    |  0.583    -   |     -     0.630   0.588   0.484 | B2  0.630     -0.048
2005.11401   Qwen    |  0.614    -   |   0.400   0.779   0.766   0.601 | B2  0.779     -0.164
2001.08361   Qwen    |  0.362    -   |   0.570   0.490   0.699   0.293 | B3  0.699     -0.336
2201.11903   Qwen    |    -      -   |   0.280   0.609   0.488   0.595 | B2  0.609          -
```

Key:
- `OV_v1` = OneVision v1 (single-pass refine, static Llama refiner)
- `OV_v2` = OneVision v2 (K=3 refine + winner-as-refiner)
- `-` = missing eval (PDF parse failure on `2106.04561`; recall-checker truncation on long papers; or v2 was killed for time-out on the 5 long papers)
- "best" column = which baseline scored highest on that paper
- "OV>best?" = `Δ(OV_best_of_v1v2 − best baseline)`, with ±0.02 tolerance for "tie"

## Outcome aggregate

| OneVision (best of v1 / v2) vs strongest baseline (per paper) | Count |
|---|---:|
| Wins by > 0.02 F1 | **7 / 27** (26 %) |
| Ties (within ±0.02) | 3 / 27 (11 %) |
| **Loses by > 0.02 F1** | **17 / 27 (63 %)** |

(Excluded: `2106.04561` PDF parse failure, `2201.11903` no OneVision
evals; n_evaluable = 27.)

Voter-vs-actually-best agreement: **14 / 27 = 52 %** — the voter's
93 %-Qwen-prefer is *not* a good per-paper model selector; on the
~48 % of papers where the actually-best baseline is B3 DeepSeek
(or sometimes B6 / B1), the voter still picks Qwen and OneVision
underperforms by 0.20–0.34 F1.

## Worst losses (4 papers where OneVision loses by > 0.30 F1)

| Paper (id, name) | Voter pick | OneVision (best) | Strongest baseline | Δ |
|---|---|---:|---|---:|
| 2305.14233 RLAIF | Llama | 0.491 | B3 DeepSeek 0.825 | **−0.334** |
| 2001.08361 Scaling Laws (Kaplan et al.) | Qwen | 0.362 | B3 DeepSeek 0.699 | **−0.336** |
| 2203.15556 Chain-of-Thought | Qwen | 0.304 | B2 Qwen-naive 0.621 | **−0.317** |
| 2010.11929 Vision Transformer | Qwen | 0.410 | B2 Qwen-naive 0.712 | **−0.302** |

Note that `2305.14233` had Llama win the vote, but DeepSeek was
actually the strongest baseline. The other three were Qwen-vote-wins
where the voter "agreed with itself" but the augmenter degraded the
output enough to lose to the cleaner Qwen-naive call.

## What this means for L9

The L9 framing is supported: the OneVision pipeline is, behaviourally,
"choose Qwen 93 % of the time + Llama-edit-the-Qwen-draft" + (in v2)
"upgrade the editor to be Qwen too." When the voter's Qwen-bias matches
the actually-best baseline, OneVision is competitive (mean 0.587 strict
≈ B2 0.645 strict, slightly behind). When it doesn't, OneVision is
catastrophically behind.

A real architectural contribution would require either:
(a) a calibrated per-paper voter (E20 NLI selector candidate), or
(b) admitting OneVision == B2 with extra steps and selling it as a
    paper about *fixed-backbone* deployment scenarios only.
