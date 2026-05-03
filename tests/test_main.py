from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_behavior_eval.main import ACTOR_SYSTEM_PROMPT, run_evaluation
from claude_behavior_eval.schemas import DimensionJudgment, EvaluationResult, MRBenchEvaluation

_R = "Dummy reason."


def _dim(passed: bool) -> DimensionJudgment:
    return DimensionJudgment(reason=_R, passed=passed)


DUMMY_SCORES = MRBenchEvaluation(
    mistake_identification=_dim(True),
    mistake_location=_dim(False),
    answer_revealing_appropriate=_dim(True),
    providing_guidance=_dim(True),
    actionability=_dim(False),
    coherence=_dim(True),
    tutor_tone=_dim(True),
    human_likeness=_dim(False),
)

DUMMY_RESULT_1 = EvaluationResult(
    item_id="item-001",
    generated_response="Think about what the discriminant tells you.",
    deterministic_passed=True,
    judge_scores=DUMMY_SCORES,
)

DUMMY_RESULT_2 = EvaluationResult(
    item_id="item-002",
    generated_response="Consider the definition carefully.",
    deterministic_passed=True,
    judge_scores=DUMMY_SCORES,
)

CSV_HEADER = [
    "id", "student_question", "target_learner_level",
    "instruction_constraints", "expected_rubric",
]


def write_dummy_csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture()
def single_row_csv(tmp_path: Path) -> Path:
    return write_dummy_csv(
        tmp_path / "input.csv",
        [
            {
                "id": "item-001",
                "student_question": "Why does x^2 + 1 have no real roots?",
                "target_learner_level": "high_school",
                "instruction_constraints": '["no direct answer"]',
                "expected_rubric": '{"coherence": "must be logical"}',
            }
        ],
    )


@pytest.fixture()
def two_row_csv(tmp_path: Path) -> Path:
    return write_dummy_csv(
        tmp_path / "input.csv",
        [
            {
                "id": "item-001",
                "student_question": "Why does x^2 + 1 have no real roots?",
                "target_learner_level": "high_school",
                "instruction_constraints": '["no direct answer"]',
                "expected_rubric": '{"coherence": "must be logical"}',
            },
            {
                "id": "item-002",
                "student_question": "What is the chain rule?",
                "target_learner_level": "undergraduate",
                "instruction_constraints": "[]",
                "expected_rubric": '{"providing_guidance": "give a hint"}',
            },
        ],
    )


class TestRunEvaluationOutputFile:
    def test_output_file_is_created(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge") as MockJudge,
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        assert output.exists()

    def test_output_contains_one_line_per_row(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge"),
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        lines = output.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_output_contains_one_line_per_row_multi(self, two_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge"),
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.side_effect = [
                DUMMY_RESULT_1, DUMMY_RESULT_2
            ]
            run_evaluation(two_row_csv, output, "dummy-actor", "dummy-judge")
        lines = output.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_each_line_is_valid_json(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge"),
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        for line in output.read_text(encoding="utf-8").strip().splitlines():
            json.loads(line)  # must not raise

    def test_json_content_matches_mocked_result(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge"),
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        line = output.read_text(encoding="utf-8").strip().splitlines()[0]
        data = json.loads(line)
        assert data["item_id"] == DUMMY_RESULT_1.item_id
        assert data["generated_response"] == DUMMY_RESULT_1.generated_response
        assert data["deterministic_passed"] == DUMMY_RESULT_1.deterministic_passed

    def test_output_parent_directory_is_created(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "nested" / "deep" / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge"),
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        assert output.exists()


class TestRunEvaluationInstantiation:
    def test_judge_instantiated_with_judge_model(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge") as MockJudge,
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        MockJudge.assert_called_once_with(model="dummy-judge")

    def test_orchestrator_instantiated_with_actor_model(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge") as MockJudge,
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        _, kwargs = MockOrch.call_args
        assert kwargs.get("actor_model") == "dummy-actor"

    def test_orchestrator_receives_judge_instance(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge") as MockJudge,
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        _, kwargs = MockOrch.call_args
        assert kwargs.get("judge") is MockJudge.return_value

    def test_custom_system_prompt_is_forwarded(self, single_row_csv: Path, tmp_path: Path):
        output = tmp_path / "results.jsonl"
        custom_prompt = "You are a Socratic tutor."
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge"),
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(
                single_row_csv, output, "dummy-actor", "dummy-judge",
                actor_system_prompt=custom_prompt,
            )
        _, kwargs = MockOrch.return_value.evaluate_single_item.call_args
        assert kwargs.get("actor_system_prompt") == custom_prompt

    def test_default_system_prompt_is_used_when_not_specified(
        self, single_row_csv: Path, tmp_path: Path
    ):
        output = tmp_path / "results.jsonl"
        with (
            patch("claude_behavior_eval.main.ClaudeRubricJudge"),
            patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch,
        ):
            MockOrch.return_value.evaluate_single_item.return_value = DUMMY_RESULT_1
            run_evaluation(single_row_csv, output, "dummy-actor", "dummy-judge")
        _, kwargs = MockOrch.return_value.evaluate_single_item.call_args
        assert kwargs.get("actor_system_prompt") == ACTOR_SYSTEM_PROMPT
