# Judge Prompt Version Log

Each row below corresponds to one candidate version of the editable judge prompt template (`judge_prompts/<version>.txt`).

All judge-development metrics are measured on the **judge DEV split only**.

A dimension passes the pre-registered D1 validation rule when:

* κ ≥ 0.40, and
* pass-precision ≥ 0.80.

See `08_judge_decision.py` for the complete decision policy.

| Version | Date       | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                       | DEV Macro F1 | DEV Mean κ | Dimensions Passing D1                                                                      |
| ------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -----------: | ---------: | ------------------------------------------------------------------------------------------ |
| **v0**  | 2026-08-26 | Initial prompt extracted verbatim from `judge.py` and used as the frozen baseline.                                                                                                                                                                                                                                                                                                                                                                           |        86.3% |       0.47 | **6/8** — excluded: `providing_guidance` (κ = 0.32), `tutor_tone` (pass-precision = 49.5%) |
| **v1**  | 2026-08-27 | Proposed by `claude-sonnet-5` from v0 DEV disagreements (`v1.rationale.md`; six systematic patterns, independently matched by manual analysis). Human-reviewed and edited in three places (`v1.review.patch`): tone criterion narrowed to explicit encouragement; identification/location clarification restated as a dataset premise; answer-revealing clarification restricted to revealing the final answer and extended to off-topic responses.          |        86.9% |       0.50 | **6/8** — excluded: `providing_guidance` (κ = 0.38), `tutor_tone` (pass-precision = 55.0%) |
| **v2**  | 2026-08-27 | Proposed by `claude-sonnet-5` from v1 DEV disagreements (`v2.rationale.md`). Accepted proposed rules 1–3; rejected 4–5. Rules 6–7 were rejected and inverted after human review because the proposer had misread the false-negative direction: v1's `coherence` and `human_likeness` clarifications had made the judge too strict, reducing recall from 96.5→86.5 and 94.9→89.3 respectively. v2 therefore softened both clarifications (`v2.review.patch`). |    **89.1%** |   **0.57** | **7/8** — excluded: `tutor_tone` (pass-precision = 63.8%)                                  |
| **v3**  | 2026-08-27 | Human-proposed diagnostic ablation from v2. Replaced only the one-line definitions of `mistake_identification` and `mistake_location` with the verbatim MRBench taxonomy questions from Maurya et al. (2025), Table 2. All other prompt content was left unchanged.                                                                                                                                                                                          |      Pending |    Pending | Pending                                                                                    |

## v2 Self-Consistency Check

* **2026-08-27:** Re-scored the judge DEV split three times with the frozen v2 judge to measure sampling variability. Pairwise label agreement was **99.2%**, with run-to-run **κ = 0.95–1.00**; only **19/1,520 labels flipped**, and **175/190 rows were identical across all eight dimensions**.
* The remaining flips were concentrated in the less sharply defined criteria, including `tutor_tone` and `actionability`, while `human_likeness` showed no flips.
* Because judge-to-human agreement is substantially lower than judge-to-judge agreement, the remaining judge–human gap is interpreted as **predominantly systematic disagreement about rubric boundaries rather than stochastic sampling noise**.
* See `stats_self_consistency.txt` and the associated repeat-run script/output.

## v3 Diagnostic Hypothesis

The v3 intervention tests whether the persistent disagreement on `mistake_identification` and `mistake_location` is attributable to rubric wording.

The two replacement definitions are:

> **mistake_identification:** “Has the tutor identified/recognized a mistake in a student’s response?”

> **mistake_location:** “Does the tutor’s response accurately point to a genuine mistake and its location?”

Source: Maurya et al. (2025), MRBench taxonomy / annotation guidelines, Table 2.

### Pre-specified interaction

The `mistake_location` question contains the word **“genuine”**, which may encourage the judge to independently re-verify the mathematics. This may conflict with the existing dataset-premise clarification instructing the judge not to re-solve the problem in order to conclude that no mistake exists.

Therefore, a decrease in `mistake_location` κ is pre-specified as evidence of this instruction interaction rather than evidence of a wording benefit.

### v3 Decision Rule

Freeze **v3** iff:

1. DEV mean κ is **strictly greater than 0.57**, and
2. all seven dimensions that passed D1 under v2 continue to pass D1 under v3.

Otherwise, freeze **v2**.

---

# Harness Notes

These changes affect evaluation robustness only; they do **not** change judge semantics or boolean scores.

* **2026-08-27:** Diagnostic `reason` fields longer than 25 words are truncated before schema validation; `passed` values are never modified.
* **2026-08-27:** `validate_judge` now writes completed rows incrementally and supports `--resume`, preventing completed API evaluations from being lost after a crash.

---

# Actor Prompt Optimization

## Training Trajectory

The actor prompt optimizer was developed only on the actor training split.

Macro pass rate over the seven optimization-visible judge dimensions:

| Stage             | Actor-train macro pass rate |
| ----------------- | --------------------------: |
| Baseline          |                       60.7% |
| After iteration 1 |                       98.4% |
| After iteration 2 |                       98.6% |

The optimization effectively saturated after the first rewrite; iteration 2 produced only a marginal additional improvement.

This training performance is **not interpreted as evidence that tutoring quality generalized**. Generalization is evaluated separately on the untouched actor test split.

`tutor_tone` was excluded from the optimization objective and therefore serves as a small unoptimized control dimension.

## Frozen Actor Prompt Selection

Before evaluating the actor on the held-out actor test split, the selected optimized prompt was fixed as the **last prompt that had actually been scored on actor training**:

`optimization_runs/iteration_2_prompt.txt`

SHA-256:

```text
241a166a948e2dade46147c7c273dd6a9ad3ba593d2153dcb13725d4e5d2fc93
```

The later file:

`optimization_runs/optimized_prompt.txt`

is the optimizer's final **unscored** output and is **not used for held-out evaluation**.

This selection was recorded before inspecting actor-test results so that the test set could not influence prompt selection.

---

# Actor Test Protocol

The frozen baseline prompt and frozen selected optimized prompt are each evaluated three times on the same held-out actor test split.

The optimized runs use:

```text
--actor-system-prompt-file optimization_runs/iteration_2_prompt.txt
```

The contents of `iteration_2_prompt.txt` must not be edited after its SHA-256 has been recorded.

Baseline-vs-optimized conclusions are made only from evaluations performed under the same final frozen judge.

Baseline results from earlier pilot runs using previous judge versions are not directly comparable because the measurement instrument changed during judge development.
