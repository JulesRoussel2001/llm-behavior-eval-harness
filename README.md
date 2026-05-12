# LLM Behavior Evaluation Harness

**A reproducible Python pipeline for evaluating and optimizing subjective LLM tutor behavior with deterministic checks, frozen rubric judging, and mini actor-critic prompt optimization.**

---

> **Disclaimer:** This is an independent portfolio/open-source project. It is not an official Anthropic project. It uses Anthropic APIs to explore reproducible evaluation workflows for subjective LLM behavior and may later be adapted into a smaller educational contribution.

---

## Why this project exists

Many LLM behaviors are subjective and hard to evaluate reproducibly. Tutor quality is not only about correctness — it also includes guidance style, tone, answer-revealing discipline, coherence, actionability, and human-likeness. Off-the-shelf benchmarks rarely capture these dimensions in an auditable way.

This project turns subjective tutor behavior into auditable signals by combining:

- **Deterministic checks** for cheap objective constraints (e.g. no direct answer revealing)
- **Strict Pydantic schemas** for structured, validated outputs
- **A frozen Claude rubric judge** calibrated against MRBench human annotations
- **Benchmark-derived splits** for judge calibration, dev validation, and held-out test
- **Mini actor-critic prompt optimization** — iteratively improving a tutor prompt based on judge feedback
- **Reproducible Markdown reports** comparing baseline vs. optimized prompts

The result is an end-to-end pipeline where each evaluation step is traceable, schema-validated, and separated by a clear checkpoint discipline.

---

## Main features

- MRBench-style preprocessing and label normalization
- Class-aware data splits for judge calibration / dev / test and actor mini train / test
- Strict Pydantic schemas for structured outputs
- Deterministic checks for cheap objective constraints
- Frozen Claude rubric judge using structured tool/schema outputs
- Prompt drift check to ensure the generated judge prompt matches `judge.py`
- Local pytest test suite with mocked API behavior
- API-backed judge validation against human annotations
- Mini actor-critic prompt optimization
- Baseline vs. optimized comparison report

---

## Tech stack

- Python 3.11+
- Pydantic v2
- pytest
- Anthropic API / Tool Use
- argparse CLIs
- JSONL + Markdown reporting

---

## Architecture overview

```
Raw MRBench JSON
  -> prepare_mrbench
  -> processed CSVs + normalized labels
  -> judge/dev/test splits
  -> generated frozen judge prompt
  -> prompt drift check
  -> frozen Claude judge validation
  -> actor mini train/test splits
  -> baseline tutor evaluation
  -> actor-critic prompt optimization
  -> optimized tutor evaluation
  -> mini_results.md comparison report
```

---

## Installation

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your_api_key_here"
```

---

## Full reproducible pipeline

### Local / preparation pipeline (no API calls)

**Step 1 — Prepare MRBench data**

```bash
PYTHONPATH=src .venv/bin/python -m claude_behavior_eval.prepare_mrbench \
  --input-json data/raw_mrbench/MRBench/MRBench_V2.json \
  --output-dir data/processed_mrbench
```

**Step 2 — Verify labels**

```bash
PYTHONPATH=src .venv/bin/python scripts/02_verify_labels.py
```

**Step 3 — Create judge/dev/test splits**

```bash
PYTHONPATH=src .venv/bin/python scripts/01_create_splits.py
```

**Step 4 — Generate frozen judge prompt**

```bash
PYTHONPATH=src .venv/bin/python scripts/03_generate_prompt.py
```

At this point, copy the generated `_SYSTEM_PROMPT` block into:

```
src/claude_behavior_eval/judge.py
```

This manual step is intentional: it requires a conscious review of the generated prompt before it is frozen into the judge. The drift check in Step 5 then verifies the paste was correct.

**Step 5 — Prompt drift check**

```bash
PYTHONPATH=src .venv/bin/python scripts/05_check_prompt_drift.py
```

Expected result:

```
PASS: judge.py prompt matches generated prompt.
```

**Step 6 — Create actor mini train/test splits**

```bash
PYTHONPATH=src .venv/bin/python scripts/04_create_actor_splits.py
```

**Step 7 — Run local test suite**

```bash
PYTHONPATH=src .venv/bin/python -m pytest --tb=short -q
```

At this point, the local/preparation pipeline is complete. All tests should pass before proceeding to API-backed steps.

---

### API-backed pipeline

**Step 8 — Judge dev validation**

```bash
PYTHONPATH=src .venv/bin/python -m claude_behavior_eval.validate_judge \
  --input-csv data/processed_mrbench/judge_dev.csv \
  --output-jsonl judge_dev_results.jsonl \
  --report-md judge_dev_report.md
```

Inspect `judge_dev_report.md` to check alignment with human annotations before touching the held-out test set.

**Step 9 — Judge held-out test validation** *(run once only, after the judge is considered acceptable)*

```bash
PYTHONPATH=src .venv/bin/python -m claude_behavior_eval.validate_judge \
  --input-csv data/processed_mrbench/judge_test.csv \
  --output-jsonl judge_test_results.jsonl \
  --report-md judge_test_report.md
```

---

### Mini actor-critic pipeline

**Step 10 — Iterative prompt optimization**

```bash
PYTHONPATH=src .venv/bin/python src/claude_behavior_eval/optimize.py \
  --input-csv data/processed_mrbench/actor_mini_train.csv \
  --iterations 3 \
  --output-dir optimization_runs
```

**Step 11 — Baseline tutor evaluation**

```bash
PYTHONPATH=src .venv/bin/python src/claude_behavior_eval/main.py \
  data/processed_mrbench/actor_mini_test.csv \
  actor_mini_baseline.jsonl
```

**Step 12 — Optimized tutor evaluation**

```bash
PYTHONPATH=src .venv/bin/python src/claude_behavior_eval/main.py \
  data/processed_mrbench/actor_mini_test.csv \
  actor_mini_optimized.jsonl \
  --actor-system-prompt-file optimization_runs/optimized_prompt.txt
```

**Step 13 — Generate comparison report**

```bash
PYTHONPATH=src .venv/bin/python src/claude_behavior_eval/report.py \
  --baseline-jsonl actor_mini_baseline.jsonl \
  --optimized-jsonl actor_mini_optimized.jsonl \
  --output-md mini_results.md
```

---

## Important checkpoints

- After **Step 5**, the prompt drift check must pass before any API-backed steps.
- After **Step 7**, all local tests must pass.
- After **Step 8**, inspect `judge_dev_report.md` before touching the held-out test set.
- **Step 9** should be run once only, after the judge is considered acceptable.
- The mini actor-critic results are a small-scale demonstration, not a broad benchmark claim.

---

## Mini results

Results from a single end-to-end run on the mini actor test split:

| Metric | Baseline | Optimized | Delta (pts) |
|---|---|---|---|
| deterministic_pass_rate | 100.0% | 100.0% | +0.0 |
| mistake_identification_pass_rate | 95.0% | 100.0% | +5.0 |
| mistake_location_pass_rate | 85.0% | 95.0% | +10.0 |
| answer_revealing_appropriate_pass_rate | 10.0% | 100.0% | +90.0 |
| providing_guidance_pass_rate | 80.0% | 100.0% | +20.0 |
| actionability_pass_rate | 100.0% | 100.0% | +0.0 |
| coherence_pass_rate | 100.0% | 100.0% | +0.0 |
| tutor_tone_pass_rate | 100.0% | 100.0% | +0.0 |
| human_likeness_pass_rate | 95.0% | 100.0% | +5.0 |
| judge_macro_pass_rate | 83.1% | 99.4% | +16.2 |

> These are mini-pipeline results on a small actor test split. They show that the pipeline can run end-to-end and detect measurable differences between baseline and optimized prompts under the frozen judge. They should not be interpreted as a broad claim that the optimized prompt generalizes to all tutoring contexts.

---

## Engineering quality

- Typed Python modules throughout (`from __future__ import annotations`)
- Pydantic v2 validation for all structured outputs
- pytest coverage with mocked API behavior (no live API calls in CI)
- CLI entry points for all pipeline stages
- Generated Markdown reports for every evaluation run
- Reproducible, class-aware split generation with a fixed seed
- Prompt drift guard to prevent silent judge/prompt desync

---

## Limitations

- The judge is a validated proxy evaluator, not objective ground truth. Results depend on judge prompt quality and schema design.
- Mini actor-critic results are small-scale and should not be extrapolated.
- Human review would be needed before high-stakes educational use.
- External judge comparison or human calibration would be useful future work.
- This is a portfolio/research artifact, not a production evaluation platform.

The main takeaway is not that the optimized prompt is universally superior, but that the harness can reproducibly detect and report behavior changes between prompt variants.
---

## Future work

- Add confidence intervals and bootstrap reporting.
- Add external judge agreement analysis.
- Add a larger held-out evaluation set.
- Add CI workflow (GitHub Actions).
- Add richer per-dimension failure visualizations.
- Package as a lesson-style version for potential contribution to prompt-evaluation educational materials.

---

## Data

The raw MRBench data (`data/raw_mrbench/`) is not included in this repository. Download it from the [MRBench repository](https://github.com/MRBench/MRBench) and place it at `data/raw_mrbench/` before running Step 1.

Processed splits (`data/processed_mrbench/`) are generated locally by running Steps 1–6 and are also excluded from the repository.
