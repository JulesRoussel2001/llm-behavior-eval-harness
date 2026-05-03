import pytest
from pydantic import ValidationError

from claude_behavior_eval.schemas import (
    DatasetItem,
    DimensionJudgment,
    EvaluationResult,
    MRBenchEvaluation,
)

_R = "Dummy reason."


def _dim(passed: bool) -> dict:
    return {"reason": _R, "passed": passed}


VALID_MRBENCH = dict(
    mistake_identification=_dim(True),
    mistake_location=_dim(False),
    answer_revealing_appropriate=_dim(True),
    providing_guidance=_dim(True),
    actionability=_dim(False),
    coherence=_dim(True),
    tutor_tone=_dim(True),
    human_likeness=_dim(False),
)

VALID_DATASET_ITEM = dict(
    id="item-001",
    student_question="Why does x^2 + 1 have no real roots?",
    target_learner_level="high_school",
    instruction_constraints=["no direct answer", "use Socratic method"],
    expected_rubric={"mistake_identification": "Student conflates roots with y-intercept"},
)

VALID_RESULT = dict(
    item_id="item-001",
    generated_response="Let's think about what the discriminant tells us.",
    deterministic_passed=True,
    judge_scores=None,
)


class TestDimensionJudgment:
    def test_valid_instantiation(self):
        obj = DimensionJudgment(reason="Response was coherent.", passed=True)
        assert obj.passed is True
        assert obj.reason == "Response was coherent."

    def test_valid_from_dict(self):
        obj = DimensionJudgment(**{"reason": "No error located.", "passed": False})
        assert obj.passed is False

    def test_rejects_int_for_passed_in_strict_mode(self):
        with pytest.raises(ValidationError):
            DimensionJudgment(reason=_R, passed=1)

    def test_rejects_string_for_passed(self):
        with pytest.raises(ValidationError):
            DimensionJudgment(reason=_R, passed="yes")

    def test_rejects_reason_longer_than_25_words(self):
        long_reason = " ".join(["word"] * 26)
        with pytest.raises(ValidationError):
            DimensionJudgment(reason=long_reason, passed=True)

    def test_accepts_reason_of_exactly_25_words(self):
        reason = " ".join(["word"] * 25)
        obj = DimensionJudgment(reason=reason, passed=True)
        assert obj.passed is True

    def test_accepts_reason_under_25_words(self):
        obj = DimensionJudgment(reason="Short reason.", passed=False)
        assert obj.passed is False


class TestMRBenchEvaluation:
    def test_valid_instantiation(self):
        obj = MRBenchEvaluation(**VALID_MRBENCH)
        assert obj.mistake_identification.passed is True
        assert obj.human_likeness.passed is False

    def test_dimension_has_reason(self):
        obj = MRBenchEvaluation(**VALID_MRBENCH)
        assert obj.coherence.reason == _R

    def test_rejects_plain_string_for_dimension(self):
        with pytest.raises(ValidationError):
            MRBenchEvaluation(**{**VALID_MRBENCH, "coherence": "yes"})

    def test_rejects_plain_int_for_dimension(self):
        with pytest.raises(ValidationError):
            MRBenchEvaluation(**{**VALID_MRBENCH, "tutor_tone": 1})

    def test_rejects_missing_field(self):
        data = {k: v for k, v in VALID_MRBENCH.items() if k != "actionability"}
        with pytest.raises(ValidationError):
            MRBenchEvaluation(**data)

    def test_accepts_dimension_judgment_instance(self):
        dj = DimensionJudgment(reason="Correct identification.", passed=True)
        obj = MRBenchEvaluation(**{**VALID_MRBENCH, "mistake_identification": dj})
        assert obj.mistake_identification.passed is True


class TestDatasetItem:
    def test_valid_instantiation(self):
        obj = DatasetItem(**VALID_DATASET_ITEM)
        assert obj.id == "item-001"
        assert obj.instruction_constraints == ["no direct answer", "use Socratic method"]

    def test_rejects_non_list_constraints(self):
        with pytest.raises(ValidationError):
            DatasetItem(**{**VALID_DATASET_ITEM, "instruction_constraints": "no direct answer"})

    def test_rejects_non_dict_rubric(self):
        with pytest.raises(ValidationError):
            DatasetItem(**{**VALID_DATASET_ITEM, "expected_rubric": ["not", "a", "dict"]})

    def test_rejects_int_id(self):
        with pytest.raises(ValidationError):
            DatasetItem(**{**VALID_DATASET_ITEM, "id": 42})


class TestEvaluationResult:
    def test_valid_with_judge_scores_none(self):
        obj = EvaluationResult(**VALID_RESULT)
        assert obj.judge_scores is None
        assert obj.deterministic_passed is True

    def test_valid_with_nested_judge_scores(self):
        scores = MRBenchEvaluation(**VALID_MRBENCH)
        obj = EvaluationResult(**{**VALID_RESULT, "judge_scores": scores})
        assert isinstance(obj.judge_scores, MRBenchEvaluation)
        assert obj.judge_scores.mistake_identification.passed is True

    def test_rejects_invalid_judge_scores_type(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_RESULT, "judge_scores": "not-a-model"})

    def test_rejects_non_bool_deterministic_passed(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_RESULT, "deterministic_passed": "true"})
