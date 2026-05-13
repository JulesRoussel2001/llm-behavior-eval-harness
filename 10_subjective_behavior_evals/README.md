# Lesson 10: Evaluating Subjective Behavior with a Frozen Rubric Judge

In lessons 1–9 you learned how to evaluate model outputs using code checks and model-graded evaluators. Those techniques work well for objective tasks — counting legs, classifying topics, summarizing text.

This lesson tackles the harder case: **subjective behavior**. Using AI tutoring as the example domain, you will learn how to turn qualities like guidance style, tone, and pedagogical discipline into reproducible, auditable evaluation signals.

## What you will build

- A **behavioral taxonomy** — 8 dimensions that capture distinct aspects of tutoring quality
- A **deterministic check** — a cheap first gate that catches obvious failures before invoking the judge
- A **frozen rubric judge** — a calibrated, locked evaluator that produces structured output via tool use
- A **mini actor-critic loop** — one iteration of prompt improvement driven by measured signals

## Prerequisites

- Completion of lessons 1–9 (especially lesson 9: custom model-graded evals)
- An Anthropic API key set in a `.env` file: `ANTHROPIC_API_KEY=your_key_here`

## Installation

```bash
pip install anthropic pydantic python-dotenv
```

## Running the lesson

Open `lesson.ipynb` and run cells in order. The full notebook makes approximately 30 API calls using Claude Haiku — the same cost-optimised model used throughout this course.

## Companion repository

The full production-grade implementation of this pipeline — with MRBench-derived data splits, F1-validated judge, prompt drift guard, and reproducible Markdown reports — is available at:

[https://github.com/julesroussel/claude-behavior-eval-harness](https://github.com/julesroussel/claude-behavior-eval-harness)
