from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MRBenchEvaluation(BaseModel):
    """Binary rubric scores across the 8 MRBench-inspired pedagogical dimensions.

    This model defines the strict JSON output schema for a frozen, rubric-based LLM
    judge. The judge is a validated proxy evaluator, not an objective ground truth:
    its scores approximate human expert judgment under the MRBench academic-tutoring
    taxonomy and should be interpreted accordingly. Each field is a binary pass/fail
    verdict for the corresponding dimension.
    """

    model_config = ConfigDict(strict=True)

    mistake_identification: bool
    mistake_location: bool
    answer_revealing_appropriate: bool
    providing_guidance: bool
    actionability: bool
    coherence: bool
    tutor_tone: bool
    human_likeness: bool


class DatasetItem(BaseModel):
    """A single evaluation sample from the benchmark-derived dataset."""

    model_config = ConfigDict(strict=True)

    id: str
    student_question: str
    target_learner_level: str
    instruction_constraints: list[str]
    expected_rubric: dict[str, str]


class EvaluationResult(BaseModel):
    """Final output of the evaluation pipeline for a single generated tutor response."""

    model_config = ConfigDict(strict=True)

    item_id: str
    generated_response: str
    deterministic_passed: bool
    judge_scores: MRBenchEvaluation | None
