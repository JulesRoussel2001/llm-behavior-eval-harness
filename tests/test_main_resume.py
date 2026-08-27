"""main.run_evaluation: incremental writes, --resume skipping, and continuing past a
malformed-judge row (judge_error). Orchestrator is mocked — no API calls."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

from claude_behavior_eval.main import run_evaluation
from claude_behavior_eval.schemas import DimensionJudgment, EvaluationResult, MRBenchEvaluation

DIMS = list(MRBenchEvaluation.model_fields.keys())
_SCORES = MRBenchEvaluation(**{d: DimensionJudgment(reason="r", passed=True) for d in DIMS})

CSV_HEADER = ["id", "student_question", "target_learner_level",
              "instruction_constraints", "expected_rubric"]


def _csv(path: Path, ids: list[str]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for i in ids:
            w.writerow({"id": i, "student_question": "q", "target_learner_level": "l",
                        "instruction_constraints": "[]", "expected_rubric": "{}"})
    return path


def _good(item_id: str) -> EvaluationResult:
    return EvaluationResult(item_id=item_id, generated_response="g",
                            deterministic_passed=True, judge_scores=_SCORES)


def _malformed(item_id: str) -> EvaluationResult:
    return EvaluationResult(item_id=item_id, generated_response="g",
                            deterministic_passed=True, judge_scores=None,
                            judge_error="malformed_tool_output")


def _rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_run_continues_and_writes_judge_error_row(tmp_path: Path):
    out = tmp_path / "out.jsonl"
    with patch("claude_behavior_eval.main.ClaudeRubricJudge"), \
         patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch:
        MockOrch.return_value.evaluate_single_item.side_effect = [_good("a"), _malformed("b")]
        run_evaluation(_csv(tmp_path / "in.csv", ["a", "b"]), out, "actor", "judge")
    rows = _rows(out)
    assert [r["item_id"] for r in rows] == ["a", "b"]          # run continued
    assert rows[1]["judge_scores"] is None
    assert rows[1]["judge_error"] == "malformed_tool_output"
    assert rows[0]["judge_error"] is None


def test_resume_skips_existing_item_ids(tmp_path: Path):
    out = tmp_path / "out.jsonl"
    with patch("claude_behavior_eval.main.ClaudeRubricJudge"), \
         patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch:
        MockOrch.return_value.evaluate_single_item.side_effect = [_good("a")]
        run_evaluation(_csv(tmp_path / "in1.csv", ["a"]), out, "actor", "judge")

    with patch("claude_behavior_eval.main.ClaudeRubricJudge"), \
         patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch:
        MockOrch.return_value.evaluate_single_item.side_effect = [_good("b")]
        run_evaluation(_csv(tmp_path / "in2.csv", ["a", "b"]), out, "actor", "judge", resume=True)
        # Only the new item 'b' is evaluated.
        assert MockOrch.return_value.evaluate_single_item.call_count == 1

    assert [r["item_id"] for r in _rows(out)] == ["a", "b"]


def test_without_resume_overwrites(tmp_path: Path):
    out = tmp_path / "out.jsonl"
    with patch("claude_behavior_eval.main.ClaudeRubricJudge"), \
         patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch:
        MockOrch.return_value.evaluate_single_item.side_effect = [_good("a")]
        run_evaluation(_csv(tmp_path / "in1.csv", ["a"]), out, "actor", "judge")
    with patch("claude_behavior_eval.main.ClaudeRubricJudge"), \
         patch("claude_behavior_eval.main.PipelineOrchestrator") as MockOrch:
        MockOrch.return_value.evaluate_single_item.side_effect = [_good("b")]
        run_evaluation(_csv(tmp_path / "in2.csv", ["b"]), out, "actor", "judge")  # no resume
    assert [r["item_id"] for r in _rows(out)] == ["b"]
