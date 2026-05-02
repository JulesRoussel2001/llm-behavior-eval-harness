import pytest
from pydantic import ValidationError

from claude_behavior_eval.schemas import DatasetItem, EvaluationResult, MRBenchEvaluation

VALID_MRBENCH = dict(
    mistake_identification=True,
    mistake_location=False,
    answer_revealing_appropriate=True,
    providing_guidance=True,
    actionability=False,
    coherence=True,
    tutor_tone=True,
    human_likeness=False,
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


class TestMRBenchEvaluation:
    def test_valid_instantiation(self):
        obj = MRBenchEvaluation(**VALID_MRBENCH)
        assert obj.mistake_identification is True
        assert obj.human_likeness is False

    def test_rejects_string_for_bool(self):
        with pytest.raises(ValidationError):
            MRBenchEvaluation(**{**VALID_MRBENCH, "coherence": "yes"})

    def test_rejects_int_for_bool_in_strict_mode(self):
        with pytest.raises(ValidationError):
            MRBenchEvaluation(**{**VALID_MRBENCH, "tutor_tone": 1})

    def test_rejects_missing_field(self):
        data = {k: v for k, v in VALID_MRBENCH.items() if k != "actionability"}
        with pytest.raises(ValidationError):
            MRBenchEvaluation(**data)


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
        assert obj.judge_scores.mistake_identification is True

    def test_rejects_invalid_judge_scores_type(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_RESULT, "judge_scores": "not-a-model"})

    def test_rejects_non_bool_deterministic_passed(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_RESULT, "deterministic_passed": "true"})
