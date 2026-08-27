# Statistics report

## Judge validation: dev

Rows: 190 (conversations: 39)

| Dimension | n | Human=True % | Acc % | 95% CI (acc) | P % | R % | F1 % | kappa |
|---|---|---|---|---|---|---|---|---|
| mistake_identification | 190 | 88.9 | 84.2 | [78.2, 89.1] | 97.3 | 84.6 | 90.5 | 0.45 |
| mistake_location | 190 | 86.8 | 81.1 | [74.7, 86.4] | 97.1 | 80.6 | 88.1 | 0.44 |
| answer_revealing_appropriate | 190 | 82.1 | 93.7 | [89.2, 96.7] | 98.6 | 93.6 | 96.1 | 0.80 |
| providing_guidance | 190 | 84.2 | 88.9 | [83.6, 93.0] | 94.8 | 91.9 | 93.3 | 0.61 |
| actionability | 190 | 71.1 | 82.1 | [75.9, 87.3] | 91.7 | 82.2 | 86.7 | 0.60 |
| coherence | 190 | 90.0 | 92.6 | [87.9, 95.9] | 97.6 | 94.2 | 95.8 | 0.64 |
| tutor_tone | 190 | 28.9 | 79.5 | [73.0, 85.0] | 63.8 | 67.3 | 65.5 | 0.51 |
| human_likeness | 190 | 93.2 | 93.7 | [89.2, 96.7] | 97.1 | 96.0 | 96.6 | 0.54 |

Macro accuracy: 87.0%  ·  Macro F1: 89.1%  ·  Mean kappa: 0.57

## Judge validation: held-out test

Rows: 201 (conversations: 40)

| Dimension | n | Human=True % | Acc % | 95% CI (acc) | P % | R % | F1 % | kappa |
|---|---|---|---|---|---|---|---|---|
| mistake_identification | 201 | 89.1 | 92.5 | [88.0, 95.8] | 98.2 | 93.3 | 95.7 | 0.68 |
| mistake_location | 201 | 86.1 | 85.1 | [79.4, 89.7] | 98.6 | 83.8 | 90.6 | 0.55 |
| answer_revealing_appropriate | 201 | 77.6 | 91.5 | [86.8, 95.0] | 96.6 | 92.3 | 94.4 | 0.77 |
| providing_guidance | 201 | 82.6 | 85.1 | [79.4, 89.7] | 92.5 | 89.2 | 90.8 | 0.51 |
| actionability | 201 | 64.2 | 82.1 | [76.1, 87.1] | 86.0 | 86.0 | 86.0 | 0.61 |
| coherence | 201 | 90.5 | 92.5 | [88.0, 95.8] | 95.1 | 96.7 | 95.9 | 0.53 |
| tutor_tone | 201 | 36.8 | 77.1 | [70.7, 82.7] | 67.1 | 74.3 | 70.5 | 0.52 |
| human_likeness | 201 | 95.5 | 95.0 | [91.0, 97.6] | 97.9 | 96.9 | 97.4 | 0.47 |

Macro accuracy: 87.6%  ·  Macro F1: 90.2%  ·  Mean kappa: 0.58
