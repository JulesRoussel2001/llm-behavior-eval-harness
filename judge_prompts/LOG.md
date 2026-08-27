# Judge Prompt Version Log

Each row is one candidate version of the editable judge prompt template
(`judge_prompts/<version>.txt`). Metrics are measured on the judge **DEV** split
only. "Dimensions passing the rule" uses the pre-registered rule
κ ≥ 0.40 AND pass-precision ≥ 0.80 (see `08_judge_decision.py`).

| version | date | change | dev macro F1 | dev mean κ | dimensions passing rule |
|---|---|---|---|---|---|
| v0 | 2026-08-26 | Initial prompt extracted verbatim from `judge.py` (frozen baseline). | 86.3% | 0.47 | 6/8 — excluded: `providing_guidance` (κ=0.32 < 0.40), `tutor_tone` (pass-precision=49.5% < 0.80) |
| v1 | 2026-08-27 | harness fix: reasons >25 words are truncated before schema validation (scores unaffected); validate_judge now writes incrementally. | — | — | — (harness fix; prompt text unchanged from v0) |
