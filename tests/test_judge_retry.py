"""Retry-on-malformed-output for the judge, and the orchestrator recording
judge_error instead of crashing. Mocked client — no API calls."""
from __future__ import annotations

from unittest.mock import MagicMock

from claude_behavior_eval.judge import ClaudeRubricJudge
from claude_behavior_eval.orchestrator import PipelineOrchestrator
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

DIMS = list(MRBenchEvaluation.model_fields.keys())
ITEM = DatasetItem(
    id="i", student_question="q", target_learner_level="l",
    instruction_constraints=[], expected_rubric={},
)


def _full_scores() -> dict:
    return {d: {"reason": "ok", "passed": True} for d in DIMS}


def _truncated_before_human_likeness() -> dict:
    # Simulates a payload cut off before the final dimension → schema-invalid.
    return {d: {"reason": "ok", "passed": True} for d in DIMS if d != "human_likeness"}


def _resp(scores: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "mrbench_evaluation"
    block.input = scores
    resp = MagicMock()
    resp.content = [block]
    return resp


def _judge_with_responses(responses: list[MagicMock]) -> ClaudeRubricJudge:
    client = MagicMock()
    client.messages.create.side_effect = responses
    return ClaudeRubricJudge(client=client)


def test_fails_validation_once_then_succeeds():
    judge = _judge_with_responses([_resp(_truncated_before_human_likeness()), _resp(_full_scores())])
    result = judge.evaluate_response(ITEM, "resp")
    assert isinstance(result, MRBenchEvaluation)          # scored normally
    assert judge.retry_count == 1                         # one retry logged
    assert judge.malformed_output_count == 0
    assert judge._client.messages.create.call_count == 2


def test_truncated_before_human_likeness_triggers_retry_path():
    judge = _judge_with_responses([_resp(_truncated_before_human_likeness()), _resp(_full_scores())])
    result = judge.evaluate_response(ITEM, "resp")
    assert result is not None
    assert result.human_likeness.passed is True           # recovered on retry
    assert judge.retry_count == 1
    assert judge.last_validation_error is not None


def test_fails_three_times_returns_none():
    bad = _truncated_before_human_likeness()
    judge = _judge_with_responses([_resp(bad), _resp(bad), _resp(bad)])
    result = judge.evaluate_response(ITEM, "resp")
    assert result is None                                  # no raise
    assert judge.malformed_output_count == 1
    assert judge.retry_count == 2                          # 2 retries after the first attempt
    assert judge._client.messages.create.call_count == 3   # no 4th attempt


def _actor_client(text: str) -> MagicMock:
    block = MagicMock(); block.type = "text"; block.text = text
    resp = MagicMock(); resp.content = [block]
    client = MagicMock(); client.messages.create.return_value = resp
    return client


def test_orchestrator_records_judge_error_when_judge_returns_none():
    judge = MagicMock()
    judge.evaluate_response.return_value = None
    orch = PipelineOrchestrator(judge=judge, actor_client=_actor_client("A helpful tutor reply."))
    result = orch.evaluate_single_item(ITEM, "prompt")
    assert result.judge_scores is None
    assert result.judge_error == "malformed_tool_output"
    assert result.deterministic_passed is True


def test_orchestrator_no_error_when_judge_scores():
    judge = MagicMock()
    judge.evaluate_response.return_value = MRBenchEvaluation(**_full_scores())
    orch = PipelineOrchestrator(judge=judge, actor_client=_actor_client("A helpful tutor reply."))
    result = orch.evaluate_single_item(ITEM, "prompt")
    assert result.judge_error is None
    assert isinstance(result.judge_scores, MRBenchEvaluation)
