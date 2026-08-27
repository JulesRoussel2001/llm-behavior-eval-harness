"""Reason truncation in ClaudeRubricJudge: long reasons are shortened to 25 words
before schema validation; `passed` verdicts are never touched."""
from __future__ import annotations

from unittest.mock import MagicMock

from claude_behavior_eval.judge import ClaudeRubricJudge, _truncate_reasons
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

DIMS = list(MRBenchEvaluation.model_fields.keys())
ITEM = DatasetItem(
    id="i", student_question="q", target_learner_level="l",
    instruction_constraints=[], expected_rubric={},
)


def _scores(long_dim: str, long_reason: str) -> dict:
    scores = {d: {"reason": "Short reason.", "passed": True} for d in DIMS}
    scores[long_dim] = {"reason": long_reason, "passed": True}
    return scores


def _client(scores: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "mrbench_evaluation"
    block.input = scores
    resp = MagicMock()
    resp.content = [block]
    client = MagicMock()
    client.messages.create.return_value = resp
    return client


def test_thirty_word_reason_truncated_to_25_passed_unchanged():
    long_reason = " ".join(f"w{i}" for i in range(30))  # 30 words
    judge = ClaudeRubricJudge(client=_client(_scores("mistake_identification", long_reason)))
    result = judge.evaluate_response(ITEM, "resp")

    reason = result.mistake_identification.reason
    assert len(reason.split()) == 25
    assert reason == " ".join(f"w{i}" for i in range(25))
    assert result.mistake_identification.passed is True   # score untouched
    assert judge.truncated_reason_count == 1


def test_short_reason_not_truncated():
    judge = ClaudeRubricJudge(client=_client(_scores("coherence", "A short reason.")))
    judge.evaluate_response(ITEM, "resp")
    assert judge.truncated_reason_count == 0


def test_count_accumulates_across_calls():
    long_reason = " ".join(str(i) for i in range(40))
    judge = ClaudeRubricJudge(client=_client(_scores("coherence", long_reason)))
    judge.evaluate_response(ITEM, "resp")
    judge.evaluate_response(ITEM, "resp")
    assert judge.truncated_reason_count == 2


def test_truncate_reasons_helper_leaves_passed_and_short_reasons():
    data = {
        "a": {"reason": " ".join(str(i) for i in range(30)), "passed": True},
        "b": {"reason": "ok short", "passed": False},
    }
    cleaned, n = _truncate_reasons(data)
    assert n == 1
    assert len(cleaned["a"]["reason"].split()) == 25
    assert cleaned["a"]["passed"] is True
    assert cleaned["b"] == {"reason": "ok short", "passed": False}
