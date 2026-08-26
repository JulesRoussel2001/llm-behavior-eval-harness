"""Tests that validate_judge writes the prompt version + sha, and that the
--judge-prompt-version path assembles a candidate prompt (via a monkeypatched
assembler, so no API and no fixture prompt files needed)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock

import claude_behavior_eval.validate_judge as vj
from claude_behavior_eval.judge import _SYSTEM_PROMPT
from claude_behavior_eval.judge_prompt import prompt_sha256
from claude_behavior_eval.schemas import MRBenchEvaluation

_DIMS = list(MRBenchEvaluation.model_fields.keys())


def _make_evaluation() -> MRBenchEvaluation:
    return MRBenchEvaluation(**{d: {"reason": "r.", "passed": True} for d in _DIMS})


def _make_judge() -> MagicMock:
    j = MagicMock()
    j.evaluate_response.return_value = _make_evaluation()
    return j


def _write_csv(tmp_path: Path) -> Path:
    fieldnames = [
        "id", "student_question", "target_learner_level",
        "instruction_constraints", "expected_rubric", "tutor_response",
    ] + [f"human_{d}" for d in _DIMS]
    row = {
        "id": "item-1", "student_question": "q", "target_learner_level": "lvl",
        "instruction_constraints": json.dumps([]), "expected_rubric": json.dumps({}),
        "tutor_response": "resp",
    }
    for d in _DIMS:
        row[f"human_{d}"] = "Encouraging" if d == "tutor_tone" else "Yes"
    path = tmp_path / "in.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerow(row)
    return path


def _run(tmp_path, version=None):
    out_jsonl = tmp_path / "out.jsonl"
    out_md = tmp_path / "out.md"
    metrics = vj.validate_judge(
        _write_csv(tmp_path), out_jsonl, out_md,
        judge=_make_judge(), judge_prompt_version=version,
    )
    rows = [json.loads(l) for l in out_jsonl.read_text().splitlines() if l.strip()]
    return metrics, rows, out_md.read_text(encoding="utf-8")


def test_without_version_uses_frozen_sha_and_null_version(tmp_path: Path):
    metrics, rows, report = _run(tmp_path, version=None)
    expected_sha = prompt_sha256(_SYSTEM_PROMPT)
    assert rows[0]["judge_prompt_version"] is None
    assert rows[0]["judge_prompt_sha256"] == expected_sha
    assert metrics["judge_prompt_sha256"] == expected_sha
    assert expected_sha in report
    assert "judge.py (frozen)" in report


def test_with_version_writes_version_and_assembled_sha(tmp_path: Path, monkeypatch):
    fake_prompt = "ASSEMBLED CANDIDATE PROMPT v9"
    monkeypatch.setattr(vj, "assemble_prompt", lambda version: fake_prompt)
    metrics, rows, report = _run(tmp_path, version="v9")
    expected_sha = prompt_sha256(fake_prompt)
    assert rows[0]["judge_prompt_version"] == "v9"
    assert rows[0]["judge_prompt_sha256"] == expected_sha
    assert metrics["judge_prompt_version"] == "v9"
    assert "v9" in report
    assert expected_sha in report
