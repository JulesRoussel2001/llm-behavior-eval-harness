from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from claude_behavior_eval.config import DEFAULT_JUDGE_MODEL
from claude_behavior_eval.judge import ClaudeRubricJudge
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

VALID_ITEM = DatasetItem(
    id="item-001",
    student_question="Why does x^2 + 1 have no real roots?",
    target_learner_level="high_school",
    instruction_constraints=["no direct answer", "use Socratic method"],
    expected_rubric={"mistake_identification": "Student conflates roots with y-intercept"},
)

_R = "Dummy reason."


def _dim(passed: bool) -> dict:
    return {"reason": _R, "passed": passed}


VALID_SCORES: dict = {
    "mistake_identification": _dim(True),
    "mistake_location": _dim(False),
    "answer_revealing_appropriate": _dim(True),
    "providing_guidance": _dim(True),
    "actionability": _dim(False),
    "coherence": _dim(True),
    "tutor_tone": _dim(True),
    "human_likeness": _dim(False),
}


def _make_tool_use_block(name: str = "mrbench_evaluation", scores: dict | None = None) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = scores if scores is not None else VALID_SCORES
    return block


def _make_text_block() -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = "Some plain text."
    return block


def _make_client(content_blocks: list[MagicMock]) -> MagicMock:
    response = MagicMock()
    response.content = content_blocks
    client = MagicMock()
    client.messages.create.return_value = response
    return client


class TestEvaluateResponseSuccess:
    def test_returns_mrbench_evaluation(self):
        client = _make_client([_make_tool_use_block()])
        judge = ClaudeRubricJudge(client=client)
        result = judge.evaluate_response(VALID_ITEM, "Let's think about the discriminant.")
        assert isinstance(result, MRBenchEvaluation)

    def test_scores_match_mock_input(self):
        client = _make_client([_make_tool_use_block()])
        judge = ClaudeRubricJudge(client=client)
        result = judge.evaluate_response(VALID_ITEM, "Let's think about the discriminant.")
        assert result.mistake_identification.passed is True
        assert result.mistake_location.passed is False
        assert result.human_likeness.passed is False

    def test_dimension_reason_propagated(self):
        client = _make_client([_make_tool_use_block()])
        judge = ClaudeRubricJudge(client=client)
        result = judge.evaluate_response(VALID_ITEM, "Let's think about the discriminant.")
        assert result.coherence.reason == _R

    def test_finds_tool_block_among_multiple_content_blocks(self):
        client = _make_client([_make_text_block(), _make_tool_use_block()])
        judge = ClaudeRubricJudge(client=client)
        result = judge.evaluate_response(VALID_ITEM, "Some response.")
        assert isinstance(result, MRBenchEvaluation)


class TestEvaluateResponseCallParameters:
    def setup_method(self):
        self.client = _make_client([_make_tool_use_block()])
        self.judge = ClaudeRubricJudge(client=self.client)
        self.judge.evaluate_response(VALID_ITEM, "Let's think about the discriminant.")
        self.call_kwargs = self.client.messages.create.call_args.kwargs

    def test_uses_correct_model(self):
        assert self.call_kwargs["model"] == DEFAULT_JUDGE_MODEL

    def test_uses_temperature_zero(self):
        assert self.call_kwargs["temperature"] == 0.0

    def test_uses_max_tokens_1024(self):
        assert self.call_kwargs["max_tokens"] == 1024

    def test_forces_tool_choice(self):
        assert self.call_kwargs["tool_choice"] == {
            "type": "tool",
            "name": "mrbench_evaluation",
        }

    def test_defines_exactly_one_tool(self):
        assert len(self.call_kwargs["tools"]) == 1

    def test_tool_name_is_mrbench_evaluation(self):
        assert self.call_kwargs["tools"][0]["name"] == "mrbench_evaluation"

    def test_tool_input_schema_matches_model_schema(self):
        assert (
            self.call_kwargs["tools"][0]["input_schema"]
            == MRBenchEvaluation.model_json_schema()
        )


class TestEvaluateResponseErrors:
    def test_raises_value_error_when_no_tool_use_block(self):
        client = _make_client([_make_text_block()])
        judge = ClaudeRubricJudge(client=client)
        with pytest.raises(ValueError):
            judge.evaluate_response(VALID_ITEM, "Some response.")

    def test_raises_value_error_when_tool_name_does_not_match(self):
        client = _make_client([_make_tool_use_block(name="wrong_tool")])
        judge = ClaudeRubricJudge(client=client)
        with pytest.raises(ValueError):
            judge.evaluate_response(VALID_ITEM, "Some response.")

    def test_raises_value_error_when_content_is_empty(self):
        client = _make_client([])
        judge = ClaudeRubricJudge(client=client)
        with pytest.raises(ValueError):
            judge.evaluate_response(VALID_ITEM, "Some response.")


class TestClientInjection:
    def test_injected_client_is_used(self):
        client = _make_client([_make_tool_use_block()])
        judge = ClaudeRubricJudge(client=client)
        judge.evaluate_response(VALID_ITEM, "Some response.")
        client.messages.create.assert_called_once()

    def test_default_client_instantiated_when_none(self, monkeypatch):
        mock_instance = _make_client([_make_tool_use_block()])
        mock_class = MagicMock(return_value=mock_instance)
        monkeypatch.setattr("claude_behavior_eval.judge.Anthropic", mock_class)

        judge = ClaudeRubricJudge(client=None)
        mock_class.assert_called_once_with()

        judge.evaluate_response(VALID_ITEM, "Some response.")
        mock_instance.messages.create.assert_called_once()

    def test_custom_model_is_forwarded(self):
        client = _make_client([_make_tool_use_block()])
        judge = ClaudeRubricJudge(client=client, model="claude-3-opus-latest")
        judge.evaluate_response(VALID_ITEM, "Some response.")
        assert client.messages.create.call_args.kwargs["model"] == "claude-3-opus-latest"
