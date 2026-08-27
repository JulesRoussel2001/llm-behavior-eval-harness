# Judge Prompt Version Log

Each row is one candidate version of the editable judge prompt template
(`judge_prompts/<version>.txt`). Metrics are measured on the judge **DEV** split
only. "Dimensions passing the rule" uses the pre-registered rule
κ ≥ 0.40 AND pass-precision ≥ 0.80 (see `08_judge_decision.py`).

| version | date | change | dev macro F1 | dev mean κ | dimensions passing rule |
|---|---|---|---|---|---|
| v0 | 2026-08-26 | Initial prompt extracted verbatim from `judge.py` (frozen baseline). | 86.3% | 0.47 | 6/8 — excluded: `providing_guidance` (κ=0.32), `tutor_tone` (pass-precision=49.5%) |
| v1 | 2026-08-27 | Proposed by claude-sonnet-5 from v0 DEV disagreements (`v1.rationale.md`, six patterns; matched an independent manual analysis). Human-edited in three places (`v1.review.patch`): tone criterion narrowed to explicit encouragement; identification/location note restated as dataset premise; revealing note restricted to the final answer and extended to off-topic responses. | 86.9% | 0.50 | 6/8 — excluded: `providing_guidance` (κ=0.38), `tutor_tone` (pass-precision=55.0%) |
| v2 | 2026-08-27 | Proposed by claude-sonnet-5 from v1 DEV disagreements (`v2.rationale.md`). Accepted rules 1–3; rejected 4–5; rules 6–7 rejected and inverted (proposer misread FN direction; v1's coherence/human-likeness notes had made the judge too strict, recall 96.5→86.5 and 94.9→89.3), so v2 softens both notes (`v2.review.patch`). | (pending) | (pending) | (pending) |
v3 — human-proposed diagnostic ablation from v2. Replaced only the
mistake_identification and mistake_location one-line definitions with the
verbatim MRBench taxonomy definitions from Maurya et al. (2025), Table 2:
“Has the tutor identified/recognized a mistake in a student’s response?” and
“Does the tutor’s response accurately point to a genuine mistake and its location?”
All other prompt content was left unchanged.

Hypothesis: test whether the persistent mistake_identification/mistake_location
disagreement is attributable to rubric wording.

Pre-specified interaction note: the mistake_location question contains the word
“genuine”, which may encourage the judge to re-verify the mathematics, potentially
conflicting with the existing dataset-premise clarification instructing it not to
re-solve the problem. A drop in mistake_location κ would therefore be interpreted
as evidence of this interaction rather than a wording benefit.

Decision rule: freeze v3 iff mean κ > 0.57 and all seven dimensions validated
under D1 in v2 remain D1-valid; otherwise freeze v2.

Harness notes (not prompt versions):
- 2026-08-27: reasons >25 words are truncated before schema validation (scores unaffected); `validate_judge` now writes rows incrementally and supports `--resume`.
