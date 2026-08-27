# Judge Development Decision

Status: pre-registered on 26 August 2026, before any candidate judge version (v1+) was run on DEV
and before the judge TEST split was evaluated by any version.

---

## 1. Pre-registered decisions

These decisions are fixed now and are not revised after seeing results. Any deviation must be
recorded in this file with a date and a reason, and reported in the paper.

**D1 — Validation rule for a judge dimension.**
A dimension is *validated* if, on the DEV results of the final frozen judge version, both hold:

- Cohen's κ ≥ 0.40 (human labels vs. judge labels, chance-corrected agreement), and
- pass-precision ≥ 0.80, where pass = True is the positive class and
  pass_precision = TP / (TP + FP).

If κ is undefined (expected agreement = 1) or precision is undefined (TP + FP = 0), the dimension
fails validation. The rule is applied by `scripts/08_judge_decision.py`, whose output
`judge_validated_dimensions.json` is the single source of truth downstream.

Rationale: κ guards against agreement that is only due to class imbalance; pass-precision is the
quantity a pass-rate-maximising optimizer can exploit, so a "pass" must mean a pass.

**D2 — Version selection.**
Among eligible candidate versions, the one with the highest mean κ over the eight dimensions on DEV
is frozen. Ties go to the version with fewer edits relative to v0. A version is eligible only if
every edit is a rubric clarification traceable to a repeated DEV disagreement and is logged in
`judge_prompts/LOG.md` with the disagreement pattern that motivated it.

**D3 — Cap on development.**
At most three new versions (v1, v2, v3). If a version does not improve mean κ over its predecessor,
the predecessor is frozen and development stops. v0 is the current prompt, already evaluated on DEV.

**D4 — Single evaluation of TEST.**
The judge TEST split is evaluated exactly once, by the frozen version, after `FROZEN` is written
and the drift check passes. TEST results are never used to revise the judge, the calibration
examples, the validation rule, or the set of validated dimensions. If TEST is disappointing, it is
reported as is.

**D5 — Validated dimensions are decided on DEV, before TEST.**
`08_judge_decision.py` is run on the frozen version's DEV results before the TEST run. The
resulting set of validated dimensions is fixed at that point.

**D6 — Excluded dimensions leave the optimizer objective.**
Dimensions that fail D1 are removed from the metrics object passed to the actor-prompt optimizer
(`optimize.py --objective-dims-file judge_validated_dimensions.json`). They are still scored and
reported for every actor run, including the actor test split, but they are not optimized against,
and their deltas are reported without interpretation.

**D7 — What does not change during development.**
The calibration split (3 rows), the DEV/TEST conversation split, the actor train/test split, the
eight dimension names and their MRBench semantics, and the structured-output format.

---

## 2. Development policy (how DEV is used)

### Goal

The judge is developed on the judge DEV split, then frozen before evaluation on the held-out judge
TEST split. The objective is not to maximise agreement with DEV labels but to identify systematic
misunderstandings of the MRBench rubric and translate them into clearer, generalisable judge
instructions.

### Judge prompt structure

Every version keeps the same structure:

1. Rubric dimensions (the eight MRBench dimensions).
2. Semantic clarifications (e.g. the binary reformulation of tutor_tone).
3. Fixed calibration examples: real MRBench rows with gold labels, loaded from the calibration
   split via `{{CALIBRATION_EXAMPLES}}`, excluded from DEV and TEST, never edited.
4. Structured-output instructions: one short observable reason per dimension, a boolean `passed`,
   no chain-of-thought.

### Versioning

Editable instructions live in `judge_prompts/vN.txt`. Each meaningful change is a new version;
nothing is overwritten. `judge_prompts/FROZEN` names the frozen version; `judge_prompts/LOG.md`
records, per version: date, the change, the DEV disagreement pattern that motivated it, DEV macro
F1, DEV mean κ, and the dimensions passing D1.

### DEV evaluation and diagnosis

For each candidate, run `validate_judge --judge-prompt-version vN` on DEV, then `06_stats.py` and
`07_disagreements.py`. Diagnostic rule: any dimension with balanced accuracy below ~0.80, or with
a visibly one-directional error pattern (precision ≪ recall or recall ≪ precision), is inspected.
This is a diagnostic threshold, not the validation rule (D1) and not an optimization target.

For an inspected dimension:

1. Read the false positives and false negatives with the judge's stated reasons.
2. Look for a repeated, interpretable disagreement with the MRBench annotators.
3. Name the rubric ambiguity behind it.
4. Write a general clarification of the rubric that resolves it, without changing what the human
   label means.
5. Save as a new version; rerun on DEV.

The judge is never told "be stricter" or "be more lenient", and never sees its own DEV metrics.
Example of the intended kind of change: if the judge repeatedly rejects concise hints under
providing_guidance because it expects a worked explanation, the clarification is "guidance does not
require a complete explanation; a concise, relevant hint that helps the student progress counts",
not "accept more responses".

### Preventing DEV overfitting

- Misclassified DEV rows are never added to the calibration examples.
- No DEV item identifiers, answers, or verbatim excerpts are encoded into the prompt.
- No rule is changed to correct an isolated example; changes require multiple disagreements or a
  clear general conceptual issue.
- Dimensions already working well are left alone absent evidence of a systematic problem.

### Roles

The *prompt analyzer* (a person, optionally assisted by an LLM) sees DEV metrics, human labels,
judge predictions, judge reasons, and FP/FN examples, and proposes rubric clarifications. The
*judge* sees only the resulting rubric, the fixed calibration examples, and the output
instructions.

### Freezing and TEST

Development ends when D2/D3 select a version. Write its name to `FROZEN`, regenerate with
`03_generate_prompt.py`, paste into `judge.py`, confirm `05_check_prompt_drift.py` passes with the
expected SHA-256, run `08_judge_decision.py` on that version's DEV results (D5), then run TEST once
(D4). Report DEV and TEST metrics separately; TEST is the generalisation estimate.

---

## 3. Log of deviations

- 2026-08-27: judge max_tokens raised 512 → 1024 after two truncated tool outputs during actor test runs. Frozen prompt (SHA 16c17879…) unchanged. This cannot alter any valid score; it only prevents truncation, which previously crashed the run. All DEV/TEST validation rows completed without truncation, so validation results are unaffected. Judge calls that still fail after 2 retries are recorded as judge_error and reported, not silently dropped.
