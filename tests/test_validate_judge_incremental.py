"""Incremental (crash-safe) JSONL writing and --resume for validate_judge."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock

from claude_behavior_eval.schemas import MRBenchEvaluation
from claude_behavior_eval.validate_judge import validate_judge

DIMS = list(MRBenchEvaluation.model_fields.keys())


def _evaluation() -> MRBenchEvaluation:
    return MRBenchEvaluation(**{d: {"reason": "r", "passed": True} for d in DIMS})


def _make_judge() -> MagicMock:
    j = MagicMock()
    j.evaluate_response.return_value = _evaluation()
    j.truncated_reason_count = 0
    return j


def _write_csv(path: Path, ids: list[str]) -> Path:
    fieldnames = [
        "id", "student_question", "target_learner_level",
        "instruction_constraints", "expected_rubric", "tutor_response",
    ] + [f"human_{d}" for d in DIMS]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i in ids:
            row = {"id": i, "student_question": "q", "target_learner_level": "l",
                   "instruction_constraints": "[]", "expected_rubric": "{}",
                   "tutor_response": "resp"}
            for d in DIMS:
                row[f"human_{d}"] = "Encouraging" if d == "tutor_tone" else "Yes"
            w.writerow(row)
    return path


def _ids_in(path: Path) -> list[str]:
    return [json.loads(l)["item_id"] for l in path.read_text().splitlines() if l.strip()]


def test_writes_one_line_per_row(tmp_path: Path):
    outj, outm = tmp_path / "out.jsonl", tmp_path / "r.md"
    validate_judge(_write_csv(tmp_path / "in.csv", ["a", "b", "c"]), outj, outm, judge=_make_judge())
    assert _ids_in(outj) == ["a", "b", "c"]


def test_resume_skips_existing_and_evaluates_only_new(tmp_path: Path):
    outj, outm = tmp_path / "out.jsonl", tmp_path / "r.md"
    validate_judge(_write_csv(tmp_path / "in1.csv", ["a", "b"]), outj, outm, judge=_make_judge())
    assert _ids_in(outj) == ["a", "b"]

    j2 = _make_judge()
    validate_judge(_write_csv(tmp_path / "in2.csv", ["a", "b", "c"]), outj, outm,
                   judge=j2, resume=True)
    assert _ids_in(outj) == ["a", "b", "c"]          # appended, no duplicates
    assert j2.evaluate_response.call_count == 1        # only 'c' was evaluated


def test_without_resume_overwrites(tmp_path: Path):
    outj, outm = tmp_path / "out.jsonl", tmp_path / "r.md"
    validate_judge(_write_csv(tmp_path / "in1.csv", ["a", "b"]), outj, outm, judge=_make_judge())
    validate_judge(_write_csv(tmp_path / "in2.csv", ["c"]), outj, outm, judge=_make_judge())
    assert _ids_in(outj) == ["c"]


def test_resume_metrics_cover_full_file(tmp_path: Path):
    outj, outm = tmp_path / "out.jsonl", tmp_path / "r.md"
    validate_judge(_write_csv(tmp_path / "in1.csv", ["a", "b"]), outj, outm, judge=_make_judge())
    metrics = validate_judge(_write_csv(tmp_path / "in2.csv", ["a", "b", "c"]), outj, outm,
                             judge=_make_judge(), resume=True)
    # All 3 rows agree (judge True, human True) → per-dimension accuracy over 3 rows.
    assert metrics["per_dimension"]["coherence"]["accuracy"] == 100.0
    assert "Reasons truncated (>25 words):" in outm.read_text(encoding="utf-8")
