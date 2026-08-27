# LLM Behavior Evaluation Harness

**A reproducible Python pipeline for validating an LLM rubric judge per dimension against human annotations, freezing it, and only then using it as an optimization signal for subjective LLM tutor behavior.**

---

> **Disclaimer:** This is an independent open-source research project. It is not an official Anthropic project. It uses Anthropic APIs to study reproducible evaluation workflows for subjective LLM behavior.

---

## Why this project exists

When an LLM judge's scores feed back into prompt optimization or training, the judge is no longer a measurement instrument but part of a control loop: its errors are not averaged out, they are optimized toward. An aggregate judge–human agreement of 87% is compatible with one criterion being near chance, and an optimizer will find that criterion first.

This harness makes a judge's fitness as an optimization signal a **per-dimension, pre-registered, auditable** property:

1. The judge is **developed on a human-labeled dev split**, with every prompt edit versioned, justified by a logged disagreement pattern, and reviewed by a human.
2. A **validation rule fixed in advance** (Cohen's κ ≥ 0.40 and pass-precision ≥ 0.80) decides which dimensions are trustworthy.
3. The judge is **frozen** (SHA-256 pinned, drift-checked at every run) and **evaluated once** on a held-out split.
4. Dimensions that fail validation are **removed from the optimizer's objective** but still scored and reported.
5. The optimized policy is evaluated on **held-out conversations** with intervals and paired tests.

The dataset is [MRBench](https://github.com/MRBench/MRBench) (Maurya et al., 2025), where each tutor response carries human labels on eight pedagogical dimensions: mistake identification, mistake location, answer revealing, providing guidance, actionability, coherence, tutor tone, and human-likeness.

---

## Results at a glance

**Judge** (Claude Haiku 4.5, frozen version v2), agreement with MRBench human labels:

| | v0 (initial) | v2 (frozen) dev | v2 held-out test |
|---|---|---|---|
| Rows (conversations) | 190 (40) | 190 (40) | 201 (40) |
| Macro F1 | 86.3% | 89.1% | 90.2% |
| Mean Cohen's κ | 0.47 | 0.57 | 0.58 |
| Dimensions passing the rule | 6 / 8 | 7 / 8 | 7 / 8 |
| Excluded dimension | guidance, tone | tone | tone |

Test-retest on identical dev rows (3 runs): 99.2% pairwise label agreement, run-to-run κ 0.95–1.00, 19 of 1,520 labels flipped. The judge–human gap is systematic, not sampling noise.

**Optimization** (Haiku 4.5 actor, Haiku 4.5 optimizer, 52 training conversations, 3 iterations), evaluated on **60 held-out conversations, 3 runs per condition**:

| Dimension | In objective | Baseline % | Optimized % | Δ (pts) | McNemar p (max of 3 runs) |
|---|---|---|---|---|---|
| mistake_identification | ✓ | 86.7 | 95.0 | +8.3 | 0.29 |
| mistake_location | ✓ | 83.9 | 91.7 | +7.8 | 0.29 |
| answer_revealing_appropriate | ✓ | 1.1 | 89.4 | +88.3 | <10⁻¹⁴ |
| providing_guidance | ✓ | 90.0 | 97.8 | +7.8 | 0.38 |
| actionability | ✓ | 27.2 | 98.9 | +71.7 | <10⁻¹¹ |
| coherence | ✓ | 94.4 | 94.4 | 0.0 | 1 |
| tutor_tone | ✗ | 66.1 | 87.8 | +21.7 | 0.036 |
| human_likeness | ✓ | 26.1 | 90.0 | +63.9 | <10⁻⁹ |
| **macro (8 dims)** | | **59.4** | **93.1** | **+33.7** | |

Training trajectory (7-dimension macro on the 52 training conversations): 60.7 → 98.4 → 98.6; one round of aggregate feedback exhausts the signal. Tone, which the optimizer never saw, moved anyway; because the judge's tone verdicts are unvalidated (pass-precision 0.67), that delta is reported but not interpreted.

Full tables with Clopper–Pearson intervals: `stats_judge.md`, `stats_actor.md`.

---

## Main features

- MRBench preprocessing and binary label normalization (rows with missing or Offensive labels excluded, counts reported)
- Conversation-disjoint splits: judge calibration (3 pinned rows) / dev (40 conv.) / test (40 conv.); actor train (52) / test (60)
- **Versioned judge prompts** (`judge_prompts/vN.txt`) with a `FROZEN` pointer, a single shared assembler, and a drift check that fails on mismatch or malformed versions
- **Judge development loop on dev**: disagreement report → LLM-proposed rubric clarifications with per-edit rationale → human review (diff logged) → new version
- **Pre-registered validation rule** applied by a script, producing `judge_validated_dimensions.json`
- Judge-guided prompt optimization whose objective contains only validated dimensions
- Strict Pydantic schemas, forced tool use, retry on malformed tool output, incremental JSONL writes with `--resume`
- Statistics: per-dimension κ, precision/recall/F1, fail-detection rate, Clopper–Pearson intervals, exact McNemar on paired items, multi-run variance, judge test-retest
- pytest suite (mocked API; no live calls in tests)

---

## Tech stack

Python 3.11+, Pydantic v2, pytest, Anthropic API (tool use), scipy, argparse CLIs, JSONL + Markdown reporting.

---

## Architecture

```
Raw MRBench JSON
  -> prepare_mrbench            (binary labels; missing / Offensive -> excluded)
  -> 01_create_splits           (calibration pinned; dev/test = 40 conv. each, all rows)
  -> 04_create_actor_splits     (52 train / 60 test from the remaining conversations)
  ---- judge development (dev only) ----
  -> validate_judge --judge-prompt-version vN   (candidate on dev)
  -> 06_stats / 07_disagreements                (per-dimension metrics, FP/FN report)
  -> 09_propose_judge_version                   (LLM-proposed vN+1 + rationale)
  -> human review -> judge_prompts/vN+1.txt, LOG.md, review patch
  ---- freeze ----
  -> FROZEN = vN -> 03_generate_prompt -> paste into judge.py -> 05_check_prompt_drift (PASS + SHA)
  -> 08_judge_decision          (pre-registered rule -> judge_validated_dimensions.json)
  -> validate_judge on judge_test.csv           (ONCE)
  -> 10_self_consistency        (test-retest on dev)
  ---- optimization with the frozen judge ----
  -> optimize.py --objective-dims-file          (validated dimensions only)
  -> main.py x3 baseline, x3 optimized on actor_test.csv
  -> 06_stats                   (intervals, McNemar, multi-run variance)
```

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your_api_key_here"
export PYTHONPATH=src
```

---

## Reproducing the pipeline

Every step below prints its outputs and asserts its invariants (disjointness, pinned calibration, drift). The commands assume the venv is active and `PYTHONPATH=src` is exported.

### A. Local preparation (no API calls)

```bash
python -m claude_behavior_eval.prepare_mrbench \
  --input-json data/raw_mrbench/MRBench/MRBench_V2.json --output-dir data/processed_mrbench   # 1
python scripts/02_verify_labels.py                                                           # 2
python scripts/01_create_splits.py                                                           # 3  writes judge_split_manifest.json
python scripts/04_create_actor_splits.py                                                     # 4
python scripts/05_check_prompt_drift.py                                                      # 5  must PASS for the version in FROZEN
python -m pytest --tb=short -q                                                               # 6
```

### B. Judge development on dev (API)

Run a candidate version without touching the frozen judge:

```bash
python -m claude_behavior_eval.validate_judge --judge-prompt-version vN \
  --input-csv data/processed_mrbench/judge_dev.csv \
  --output-jsonl judge_dev_results_vN.jsonl --report-md judge_dev_report_vN.md               # 7
python scripts/06_stats.py --judge-dev judge_dev_results_vN.jsonl --output-md stats_dev_vN.md  # 8
python scripts/07_disagreements.py --input judge_dev_results_vN.jsonl --output disagreements_vN.md  # 9
python scripts/09_propose_judge_version.py --current judge_prompts/vN.txt \
  --stats stats_dev_vN.md --disagreements disagreements_vN.md \
  --out judge_prompts/vN+1.candidate.txt --rationale judge_prompts/vN+1.rationale.md \
  --model claude-sonnet-5                                                                    # 10 (one call)
```

Review the candidate, save the accepted text as `judge_prompts/vN+1.txt`, record the review diff and a LOG.md entry, and return to step 7. The rules governing this loop (validation rule, version selection by mean κ, cap of three versions, single test evaluation) are in `judge_decision.md` and were committed before any candidate ran.

### C. Freeze and held-out test (API, test once)

```bash
echo vN > judge_prompts/FROZEN
python scripts/03_generate_prompt.py          # paste the printed block into src/claude_behavior_eval/judge.py
python scripts/05_check_prompt_drift.py       # PASS + version + SHA-256
python scripts/08_judge_decision.py --input judge_dev_results_vN.jsonl   # -> judge_validated_dimensions.json
python -m claude_behavior_eval.validate_judge \
  --input-csv data/processed_mrbench/judge_test.csv \
  --output-jsonl judge_test_results.jsonl --report-md judge_test_report.md                   # ONCE
python scripts/06_stats.py --judge-dev judge_dev_results_vN.jsonl \
  --judge-test judge_test_results.jsonl --output-md stats_judge.md
```

Optional test-retest (dev only, never test):

```bash
for k in 2 3; do python -m claude_behavior_eval.validate_judge \
  --input-csv data/processed_mrbench/judge_dev.csv \
  --output-jsonl judge_dev_results_vN_rep$k.jsonl --report-md judge_dev_report_vN_rep$k.md; done
python scripts/10_self_consistency.py judge_dev_results_vN.jsonl judge_dev_results_vN_rep2.jsonl judge_dev_results_vN_rep3.jsonl
```

### D. Optimization with the frozen judge (API)

```bash
python src/claude_behavior_eval/optimize.py \
  --input-csv data/processed_mrbench/actor_train.csv --iterations 3 \
  --output-dir optimization_runs --objective-dims-file judge_validated_dimensions.json
for k in 1 2 3; do python src/claude_behavior_eval/main.py \
  data/processed_mrbench/actor_test.csv actor_baseline_run$k.jsonl; done
for k in 1 2 3; do python src/claude_behavior_eval/main.py \
  data/processed_mrbench/actor_test.csv actor_optimized_run$k.jsonl \
  --actor-system-prompt-file optimization_runs/iteration_2_prompt.txt; done
python scripts/06_stats.py \
  --baseline  actor_baseline_run1.jsonl  actor_baseline_run2.jsonl  actor_baseline_run3.jsonl \
  --optimized actor_optimized_run1.jsonl actor_optimized_run2.jsonl actor_optimized_run3.jsonl \
  --output-md stats_actor.md
```

The evaluated prompt is the last *train-scored* iteration (`iteration_2_prompt.txt`); the optimizer's final unscored output (`optimized_prompt.txt`) is not used.

---

## Checkpoint discipline

- `05_check_prompt_drift.py` must PASS (version + SHA-256) before any run that uses the frozen judge.
- Candidate judge versions run through `--judge-prompt-version`; `judge.py` and `FROZEN` change only at freeze time.
- `08_judge_decision.py` runs on the frozen version's **dev** results, before test.
- The judge test split is evaluated **once**. Its results are never used to revise the judge, the rule, or the validated set.
- `optimize.py` receives only validated dimensions; excluded dimensions are still scored and reported.
- Any deviation is logged with a date in `judge_decision.md` §3 (currently: judge `max_tokens` raised 512 → 1024 after truncated tool outputs; scores unaffected).

---

## Repository layout

```
src/claude_behavior_eval/   judge.py (frozen prompt), judge_prompt.py (assembler), validate_judge.py,
                            optimize.py, main.py, orchestrator.py, schemas.py, report.py, ...
scripts/                    01–10 as above
judge_prompts/              v0.txt … v3.txt, FROZEN, LOG.md, vN.candidate.txt, vN.rationale.md, vN.review.patch
judge_decision.md           pre-registered rules + deviation log
judge_validated_dimensions.json
tests/                      pytest suite (mocked API)
pilot/                      archived first run (20/10 judge rows, 20-item actor test), not used in results
```

---

## Limitations

- **Single model family.** Judge, actor, and optimizer are all Claude Haiku 4.5, so self-preference is possible. Human validation is the mitigation, but validation used responses from other tutor models (MRBench), so the judge is deployed on a response distribution it was not validated on.
- **One annotation per row.** MRBench provides a single human label, so judge error cannot be separated from annotator disagreement.
- **Clear-cut labels only.** MRBench's "To some extent" is excluded, so the judge is validated on unambiguous cases.
- **Location accuracy.** Instructing the judge not to re-solve problems fixed its largest error but means it cannot verify that a tutor points at the *right* step. A tutor rewarded for "identifying errors clearly" has an incentive to find one; the pilot showed a case of an invented error being credited.
- **Scale.** One dataset, one optimizer, 60 held-out conversations. This is a protocol case study, not a claim about tutoring.

---

## Data

The raw MRBench data (`data/raw_mrbench/`) is not included. Download it from the [MRBench repository](https://github.com/MRBench/MRBench) and place it at `data/raw_mrbench/` before step 1. Processed splits (`data/processed_mrbench/`) are generated locally and excluded from the repository; `judge_split_manifest.json` records the conversation ids and row counts of every split.

---

## Citation

If you use this harness, please cite the accompanying workshop paper (details to follow).
