from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from claude_behavior_eval.orchestrator import PipelineOrchestrator
from claude_behavior_eval.schemas import DatasetItem, EvaluationResult, MRBenchEvaluation

ACTOR_SYSTEM_PROMPT = "You are a helpful academic tutor."

_R = "Dummy reason."


def _dim(passed: bool) -> dict:
    return {"reason": _R, "passed": passed}


VALID_SCORES = MRBenchEvaluation(
    mistake_identification=_dim(True),
    mistake_location=_dim(True),
    answer_revealing_appropriate=_dim(False),
    providing_guidance=_dim(True),
    actionability=_dim(True),
    coherence=_dim(True),
    tutor_tone=_dim(True),
    human_likeness=_dim(False),
)

ITEM_NO_CONSTRAINTS = DatasetItem(
    id="item-001",
    student_question="Why does x^2 + 1 have no real roots?",
    target_learner_level="high_school",
    instruction_constraints=[],
    expected_rubric={"coherence": "must be logical"},
)

ITEM_NO_ROLEPLAY = DatasetItem(
    id="item-002",
    student_question="What is the chain rule?",
    target_learner_level="undergraduate",
    instruction_constraints=["no_roleplay"],
    expected_rubric={"providing_guidance": "give a hint"},
)


def _make_actor_client(text: str) -> MagicMock:
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response = MagicMock()
    response.content = [text_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def _make_actor_client_no_text() -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    response = MagicMock()
    response.content = [tool_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def _make_judge(scores: MRBenchEvaluation = VALID_SCORES) -> MagicMock:
    judge = MagicMock()
    judge.evaluate_response.return_value = scores
    return judge


class TestSuccessPath:
    def test_returns_evaluation_result(self):
        actor = _make_actor_client("Let's think about the discriminant.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        assert isinstance(result, EvaluationResult)

    def test_deterministic_passed_is_true(self):
        actor = _make_actor_client("Let's think about the discriminant.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        assert result.deterministic_passed is True

    def test_judge_scores_match_mock(self):
        actor = _make_actor_client("Let's think about the discriminant.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        assert result.judge_scores == VALID_SCORES

    def test_judge_called_exactly_once(self):
        actor = _make_actor_client("Let's think about the discriminant.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        judge.evaluate_response.assert_called_once()

    def test_item_id_propagated(self):
        actor = _make_actor_client("Some tutor response.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        assert result.item_id == ITEM_NO_CONSTRAINTS.id

    def test_generated_response_propagated(self):
        text = "Let's think about the discriminant."
        actor = _make_actor_client(text)
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        assert result.generated_response == text

    def test_actor_called_with_correct_parameters(self):
        actor = _make_actor_client("Some response.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        kwargs = actor.messages.create.call_args.kwargs
        assert kwargs["system"] == ACTOR_SYSTEM_PROMPT
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 512


class TestNoRoleplayDeterministicFailure:
    def test_deterministic_passed_is_false(self):
        actor = _make_actor_client("*sigh* Let me help you with that.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_ROLEPLAY, ACTOR_SYSTEM_PROMPT)
        assert result.deterministic_passed is False

    def test_judge_scores_is_none(self):
        actor = _make_actor_client("*sigh* Let me help you with that.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_ROLEPLAY, ACTOR_SYSTEM_PROMPT)
        assert result.judge_scores is None

    def test_judge_never_called(self):
        actor = _make_actor_client("*sigh* Let me help you with that.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        orch.evaluate_single_item(ITEM_NO_ROLEPLAY, ACTOR_SYSTEM_PROMPT)
        judge.evaluate_response.assert_not_called()

    def test_item_id_still_propagated(self):
        actor = _make_actor_client("[laughs] Good question!")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_ROLEPLAY, ACTOR_SYSTEM_PROMPT)
        assert result.item_id == ITEM_NO_ROLEPLAY.id


class TestNoGlobalFiltering:
    def test_roleplay_without_constraint_still_calls_judge(self):
        # no_roleplay not in instruction_constraints — marker should not block the judge
        actor = _make_actor_client("*sigh* Let me explain this concept.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        result = orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        judge.evaluate_response.assert_called_once()
        assert result.deterministic_passed is True


class TestMissingActorText:
    def test_raises_value_error_when_no_text_block(self):
        actor = _make_actor_client_no_text()
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        with pytest.raises(ValueError):
            orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)

    def test_judge_not_called_on_missing_text(self):
        actor = _make_actor_client_no_text()
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        with pytest.raises(ValueError):
            orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        judge.evaluate_response.assert_not_called()


class TestClientInjection:
    def test_injected_actor_client_is_used(self):
        actor = _make_actor_client("Some response.")
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=actor)
        orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        actor.messages.create.assert_called_once()

    def test_default_actor_client_instantiated_when_none(self, monkeypatch):
        mock_instance = _make_actor_client("Some response.")
        mock_class = MagicMock(return_value=mock_instance)
        monkeypatch.setattr("claude_behavior_eval.orchestrator.Anthropic", mock_class)
        judge = _make_judge()
        orch = PipelineOrchestrator(judge=judge, actor_client=None)
        mock_class.assert_called_once_with()
        orch.evaluate_single_item(ITEM_NO_CONSTRAINTS, ACTOR_SYSTEM_PROMPT)
        mock_instance.messages.create.assert_called_once()
