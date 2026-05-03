from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DimensionJudgment(BaseModel):
    """Structured judgment for a single MRBench pedagogical dimension."""

    model_config = ConfigDict(strict=True)

    reason: str = Field(
        description=(
            "A single concise diagnostic sentence, maximum 25 words, "
            "describing the observable success or failure."
        )
    )
    passed: bool

    @field_validator("reason")
    @classmethod
    def reason_max_25_words(cls, v: str) -> str:
        if len(v.split()) > 25:
            raise ValueError("reason must be 25 words or fewer")
        return v


class MRBenchEvaluation(BaseModel):
    """Structured diagnostic judgments across the 8 MRBench-inspired pedagogical dimensions.

    This model defines the strict JSON output schema for a frozen, rubric-based LLM
    judge. The judge is a validated proxy evaluator, not an objective ground truth:
    its scores approximate expert human judgment under the MRBench academic-tutoring
    taxonomy and should be interpreted accordingly. Each field returns a DimensionJudgment
    containing a short observable diagnostic reason and a binary pass/fail verdict.
    """

    mistake_identification: DimensionJudgment
    mistake_location: DimensionJudgment
    answer_revealing_appropriate: DimensionJudgment
    providing_guidance: DimensionJudgment
    actionability: DimensionJudgment
    coherence: DimensionJudgment
    tutor_tone: DimensionJudgment
    human_likeness: DimensionJudgment


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
