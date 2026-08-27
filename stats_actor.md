# Statistics report

## Actor evaluation: baseline vs optimized

Runs: 3 baseline, 3 optimized; items per run: [60, 60, 60] / [60, 60, 60]

| Dimension | Baseline % (mean [min, max]) | 95% CI run 1 | Optimized % (mean [min, max]) | 95% CI run 1 | Delta (pts) | Discordant b→o / o→b (pooled) | McNemar p (per run) |
|---|---|---|---|---|---|---|---|
| mistake_identification | 86.7 [83.3, 90.0] | [79.5, 96.2] | 95.0 [93.3, 96.7] | [88.5, 99.6] | +8.3 | 19 / 4 | 0.29, 0.031, 0.18 |
| mistake_location | 83.9 [81.7, 85.0] | [73.4, 92.9] | 91.7 [90.0, 93.3] | [83.8, 98.2] | +7.8 | 18 / 4 | 0.18, 0.062, 0.29 |
| answer_revealing_appropriate | 1.1 [0.0, 1.7] | [0.0, 8.9] | 89.4 [85.0, 93.3] | [73.4, 92.9] | +88.3 | 159 / 0 | 1.8e-15, 1.1e-16, 5.6e-17 |
| providing_guidance | 90.0 [86.7, 93.3] | [83.8, 98.2] | 97.8 [96.7, 98.3] | [91.1, 100.0] | +7.8 | 16 / 2 | 0.38, 0.22, 0.016 |
| actionability | 27.2 [26.7, 28.3] | [17.5, 41.4] | 98.9 [98.3, 100.0] | [91.1, 100.0] | +71.7 | 130 / 1 | 5.1e-12, 1.1e-13, 2.3e-13 |
| coherence | 94.4 [93.3, 95.0] | [86.1, 99.0] | 94.4 [93.3, 95.0] | [86.1, 99.0] | +0.0 | 9 / 9 | 1, 1, 1 |
| tutor_tone | 66.1 [61.7, 68.3] | [55.0, 79.7] | 87.8 [81.7, 95.0] | [75.4, 94.1] | +21.7 | 55 / 16 | 0.035, 0.0004, 0.036 |
| human_likeness | 26.1 [23.3, 28.3] | [17.5, 41.4] | 90.0 [88.3, 91.7] | [77.4, 95.2] | +63.9 | 118 / 3 | 2.8e-10, 1e-11, 7.5e-11 |

Macro pass rate (mean over runs): baseline 59.4% → optimized 93.1% (+33.7 pts)

McNemar: exact binomial test on discordant pairs (item passes under exactly one prompt), paired by item_id within run k. Intervals are Clopper–Pearson 95%.
