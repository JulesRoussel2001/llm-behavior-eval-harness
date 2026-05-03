from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from claude_behavior_eval.optimize import (
    calculate_metrics,
    generate_improved_prompt,
    run_optimization_loop,
)
from claude_behavior_eval.schemas import MRBenchEvaluation

_JUDGE_DIMENSIONS = list(MRBenchEvaluation.model_fields.keys())

_R = "Dummy reason."
_DIM_TRUE = {"reason": _R, "passed": True}
_DIM_FALSE = {"reason": _R, "passed": False}

_ALL_TRUE_SCORES = {dim: _DIM_TRUE for dim in _JUDGE_DIMENSIONS}
_ALL_FALSE_SCORES = {dim: _DIM_FALSE for dim in _JUDGE_DIMENSIONS}


def _make_jsonl_row(item_id: str, det_passed: bool, scores: dict | None) -> str:
    return json.dumps({
        "item_id": item_id,
        "generated_response": f"Response for {item_id}",
        "deterministic_passed": det_passed,
        "judge_scores": scores,
    })


@pytest.fixture()
def two_row_jsonl(tmp_path: Path) -> Path:
    path = tmp_path / "results.jsonl"
    path.write_text(
        _make_jsonl_row("item-001", det_passed=True, scores=_ALL_TRUE_SCORES) + "\n"
        + _make_jsonl_row("item-002", det_passed=False, scores=None) + "\n",
        encoding="utf-8",
    )
    return path


class TestCalculateMetrics:
    def test_returns_dict(self, two_row_jsonl: Path):
        result = calculate_metrics(two_row_jsonl)
        assert isinstance(result, dict)

    def test_deterministic_pass_rate_fifty_percent(self, two_row_jsonl: Path):
        result = calculate_metrics(two_row_jsonl)
        assert result["deterministic_pass_rate"] == 50.0

    def test_dimension_pass_rate_fifty_percent_when_one_of_two_passes(self, two_row_jsonl: Path):
        result = calculate_metrics(two_row_jsonl)
        for dim in _JUDGE_DIMENSIONS:
            assert result[f"{dim}_pass_rate"] == 50.0, f"Expected 50.0 for {dim}_pass_rate"

    def test_judge_macro_pass_rate_is_average_of_dimensions(self, two_row_jsonl: Path):
        result = calculate_metrics(two_row_jsonl)
        expected = sum(result[f"{dim}_pass_rate"] for dim in _JUDGE_DIMENSIONS) / len(_JUDGE_DIMENSIONS)
        assert result["judge_macro_pass_rate"] == expected

    def test_judge_macro_pass_rate_fifty_percent(self, two_row_jsonl: Path):
        result = calculate_metrics(two_row_jsonl)
        assert result["judge_macro_pass_rate"] == 50.0

    def test_none_judge_scores_counted_as_all_false(self, tmp_path: Path):
        path = tmp_path / "none_scores.jsonl"
        path.write_text(
            _make_jsonl_row("item-001", det_passed=True, scores=None) + "\n",
            encoding="utf-8",
        )
        result = calculate_metrics(path)
        for dim in _JUDGE_DIMENSIONS:
            assert result[f"{dim}_pass_rate"] == 0.0

    def test_all_passing_gives_hundred_percent(self, tmp_path: Path):
        path = tmp_path / "all_pass.jsonl"
        path.write_text(
            _make_jsonl_row("item-001", det_passed=True, scores=_ALL_TRUE_SCORES) + "\n",
            encoding="utf-8",
        )
        result = calculate_metrics(path)
        assert result["deterministic_pass_rate"] == 100.0
        assert result["judge_macro_pass_rate"] == 100.0

    def test_empty_file_returns_empty_dict(self, tmp_path: Path):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        result = calculate_metrics(path)
        assert result == {}

    def test_contains_all_expected_keys(self, two_row_jsonl: Path):
        result = calculate_metrics(two_row_jsonl)
        assert "deterministic_pass_rate" in result
        assert "judge_macro_pass_rate" in result
        for dim in _JUDGE_DIMENSIONS:
            assert f"{dim}_pass_rate" in result

    def test_nested_passed_field_is_used(self, tmp_path: Path):
        # Only "passed" inside the nested dict should count, not the dict itself
        scores = {dim: _DIM_FALSE for dim in _JUDGE_DIMENSIONS}
        path = tmp_path / "all_false.jsonl"
        path.write_text(
            _make_jsonl_row("item-001", det_passed=True, scores=scores) + "\n",
            encoding="utf-8",
        )
        result = calculate_metrics(path)
        assert result["judge_macro_pass_rate"] == 0.0


class TestGenerateImprovedPrompt:
    def _make_client(self, text: str) -> MagicMock:
        block = MagicMock()
        block.type = "text"
        block.text = text
        response = MagicMock()
        response.content = [block]
        client = MagicMock()
        client.messages.create.return_value = response
        return client

    def test_returns_text_from_response(self):
        client = self._make_client("You are a Socratic tutor.")
        result = generate_improved_prompt(client, "Old prompt.", {"coherence_pass_rate": 40.0})
        assert result == "You are a Socratic tutor."

    def test_calls_create_with_correct_model(self):
        client = self._make_client("New prompt.")
        generate_improved_prompt(client, "Old.", {}, model="test-model")
        assert client.messages.create.call_args.kwargs["model"] == "test-model"

    def test_calls_create_with_temperature_point_two(self):
        client = self._make_client("New prompt.")
        generate_improved_prompt(client, "Old.", {})
        assert client.messages.create.call_args.kwargs["temperature"] == 0.2

    def test_calls_create_with_max_tokens_1024(self):
        client = self._make_client("New prompt.")
        generate_improved_prompt(client, "Old.", {})
        assert client.messages.create.call_args.kwargs["max_tokens"] == 1024

    def test_current_prompt_included_in_user_message(self):
        client = self._make_client("New prompt.")
        generate_improved_prompt(client, "My special prompt.", {})
        user_content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "My special prompt." in user_content

    def test_metrics_included_in_user_message(self):
        client = self._make_client("New prompt.")
        metrics = {"coherence_pass_rate": 33.3}
        generate_improved_prompt(client, "Prompt.", metrics)
        user_content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "coherence_pass_rate" in user_content

    def test_raises_value_error_when_no_text_block(self):
        block = MagicMock()
        block.type = "tool_use"
        response = MagicMock()
        response.content = [block]
        client = MagicMock()
        client.messages.create.return_value = response
        with pytest.raises(ValueError):
            generate_improved_prompt(client, "Prompt.", {})


class TestRunOptimizationLoop:
    def test_run_evaluation_called_once_per_iteration(self, tmp_path: Path):
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation") as mock_run,
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Better."),
        ):
            run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=3,
                output_dir=tmp_path / "runs",
            )
        assert mock_run.call_count == 3

    def test_run_evaluation_uses_correct_output_paths(self, tmp_path: Path):
        output_dir = tmp_path / "runs"
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation") as mock_run,
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Better."),
        ):
            run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=2,
                output_dir=output_dir,
            )
        paths = [c.kwargs["output_jsonl"] for c in mock_run.call_args_list]
        assert paths[0] == output_dir / "iteration_0_results.jsonl"
        assert paths[1] == output_dir / "iteration_1_results.jsonl"

    def test_prompt_files_created_for_each_iteration(self, tmp_path: Path):
        output_dir = tmp_path / "runs"
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation"),
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Better."),
        ):
            run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=2,
                output_dir=output_dir,
            )
        assert (output_dir / "iteration_0_prompt.txt").exists()
        assert (output_dir / "iteration_1_prompt.txt").exists()

    def test_iteration_zero_prompt_file_contains_initial_prompt(self, tmp_path: Path):
        output_dir = tmp_path / "runs"
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation"),
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Better."),
        ):
            run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=1,
                output_dir=output_dir,
            )
        content = (output_dir / "iteration_0_prompt.txt").read_text(encoding="utf-8")
        assert content == "Initial."

    def test_optimized_prompt_file_is_created(self, tmp_path: Path):
        output_dir = tmp_path / "runs"
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation"),
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Final."),
        ):
            run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=1,
                output_dir=output_dir,
            )
        assert (output_dir / "optimized_prompt.txt").exists()

    def test_optimized_prompt_file_contains_final_prompt(self, tmp_path: Path):
        output_dir = tmp_path / "runs"
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation"),
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Final."),
        ):
            run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=1,
                output_dir=output_dir,
            )
        content = (output_dir / "optimized_prompt.txt").read_text(encoding="utf-8")
        assert content == "Final."

    def test_returns_final_prompt(self, tmp_path: Path):
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation"),
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Final."),
        ):
            result = run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=1,
                output_dir=tmp_path / "runs",
            )
        assert result == "Final."

    def test_output_dir_is_created(self, tmp_path: Path):
        output_dir = tmp_path / "nested" / "runs"
        with (
            patch("claude_behavior_eval.optimize.Anthropic"),
            patch("claude_behavior_eval.optimize.run_evaluation"),
            patch("claude_behavior_eval.optimize.calculate_metrics", return_value={}),
            patch("claude_behavior_eval.optimize.generate_improved_prompt", return_value="Better."),
        ):
            run_optimization_loop(
                input_csv=tmp_path / "data.csv",
                initial_prompt="Initial.",
                iterations=1,
                output_dir=output_dir,
            )
        assert output_dir.exists()
