from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_behavior_eval.schemas import MRBenchEvaluation
from claude_behavior_eval.validate_judge import (
    compute_binary_metrics,
    parse_human_label,
    parse_tone_label,
    validate_judge,
)

_DIMS = list(MRBenchEvaluation.model_fields.keys())


def _dim(passed: bool, reason: str = "Dummy reason.") -> dict:
    return {"reason": reason, "passed": passed}


def _make_evaluation(**override_passed: bool) -> MRBenchEvaluation:
    fields = {dim: _dim(override_passed.get(dim, True)) for dim in _DIMS}
    return MRBenchEvaluation(**fields)


def _make_csv(tmp_path: Path, rows: list[dict]) -> Path:
    fieldnames = [
        "id", "student_question", "target_learner_level",
        "instruction_constraints", "expected_rubric", "tutor_response",
    ] + [f"human_{dim}" for dim in _DIMS]

    path = tmp_path / "validation.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _default_row(
    item_id: str,
    *,
    human_values: dict[str, str] | None = None,
    tutor_response: str = "The answer is four.",
) -> dict:
    row: dict = {
        "id": item_id,
        "student_question": "What is 2+2?",
        "target_learner_level": "math_student",
        "instruction_constraints": json.dumps([]),
        "expected_rubric": json.dumps({}),
        "tutor_response": tutor_response,
    }
    overrides = human_values or {}
    for dim in _DIMS:
        if dim == "tutor_tone":
            # tutor_tone uses Encouraging/Neutral (not Yes/No) — default to Encouraging=True
            row[f"human_{dim}"] = overrides.get(dim, "Encouraging")
        else:
            row[f"human_{dim}"] = overrides.get(dim, "Yes")
    return row


class TestParseHumanLabel:
    @pytest.mark.parametrize("value", ["Yes", "yes", "TRUE", "true", "1"])
    def test_truthy_values(self, value: str):
        assert parse_human_label(value) is True

    @pytest.mark.parametrize("value", ["No", "no", "FALSE", "false", "0"])
    def test_falsy_values(self, value: str):
        assert parse_human_label(value) is False

    def test_raises_for_unknown_label(self):
        with pytest.raises(ValueError):
            parse_human_label("maybe")

    def test_raises_for_empty_string(self):
        with pytest.raises(ValueError):
            parse_human_label("")

    def test_raises_for_wrong_case(self):
        with pytest.raises(ValueError):
            parse_human_label("YES")

    def test_raises_for_whitespace_only(self):
        with pytest.raises(ValueError):
            parse_human_label("   ")


class TestParseToneLabel:
    def test_encouraging_is_true(self):
        assert parse_tone_label("Encouraging") is True

    def test_neutral_is_false(self):
        assert parse_tone_label("Neutral") is False

    def test_offensive_raises_value_error(self):
        with pytest.raises(ValueError, match="Offensive"):
            parse_tone_label("Offensive")

    def test_empty_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_tone_label("")

    def test_yes_raises_value_error(self):
        # Yes/No are not valid tone labels
        with pytest.raises(ValueError):
            parse_tone_label("Yes")

    def test_unknown_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_tone_label("Sarcastic")

    def test_strips_whitespace(self):
        assert parse_tone_label("  Encouraging  ") is True
        assert parse_tone_label("  Neutral  ") is False


class TestComputeBinaryMetrics:
    def test_all_correct(self):
        y_true = [True, False, True, False]
        y_pred = [True, False, True, False]
        m = compute_binary_metrics(y_true, y_pred)
        assert m["accuracy"] == 100.0
        assert m["precision"] == 100.0
        assert m["recall"] == 100.0
        assert m["f1"] == 100.0

    def test_all_wrong_positives(self):
        y_true = [True, True]
        y_pred = [False, False]
        m = compute_binary_metrics(y_true, y_pred)
        assert m["accuracy"] == 0.0
        assert m["recall"] == 0.0

    def test_known_values(self):
        # tp=2, fp=1, fn=1, tn=1  →  acc=60%, prec=recall=f1=66.67%
        y_true = [True, True, False, False, True]
        y_pred = [True, True, True, False, False]
        m = compute_binary_metrics(y_true, y_pred)
        assert m["accuracy"] == pytest.approx(60.0)
        assert m["precision"] == pytest.approx(200 / 3, rel=1e-3)
        assert m["recall"] == pytest.approx(200 / 3, rel=1e-3)
        assert m["f1"] == pytest.approx(200 / 3, rel=1e-3)

    def test_zero_precision_when_no_positives_predicted(self):
        y_true = [True, True]
        y_pred = [False, False]
        m = compute_binary_metrics(y_true, y_pred)
        assert m["precision"] == 0.0
        assert m["f1"] == 0.0

    def test_zero_recall_when_no_true_positives(self):
        y_true = [False, False]
        y_pred = [True, True]
        m = compute_binary_metrics(y_true, y_pred)
        assert m["recall"] == 0.0

    def test_empty_lists_returns_zeros(self):
        m = compute_binary_metrics([], [])
        assert m["accuracy"] == 0.0
        assert m["precision"] == 0.0
        assert m["recall"] == 0.0
        assert m["f1"] == 0.0

    def test_returns_percentages_in_range(self):
        y_true = [True, False, True]
        y_pred = [True, True, False]
        m = compute_binary_metrics(y_true, y_pred)
        assert all(0.0 <= v <= 100.0 for v in m.values())


class TestValidateJudge:
    def _make_judge(self, **override_passed: bool) -> MagicMock:
        mock_judge = MagicMock()
        mock_judge.evaluate_response.return_value = _make_evaluation(**override_passed)
        return mock_judge

    def test_writes_jsonl_output(self, tmp_path: Path):
        rows = [_default_row("item-1"), _default_row("item-2")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        assert output_jsonl.exists()
        lines = [l for l in output_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2

    def test_jsonl_contains_expected_fields(self, tmp_path: Path):
        rows = [_default_row("item-1")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        record = json.loads(output_jsonl.read_text(encoding="utf-8").splitlines()[0])
        assert record["item_id"] == "item-1"
        for field in ("human_labels", "judge_labels", "judge_reasons", "matches", "tutor_response_excerpt"):
            assert field in record

    def test_writes_markdown_report(self, tmp_path: Path):
        rows = [_default_row("item-1"), _default_row("item-2")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        assert report_md.exists()
        content = report_md.read_text(encoding="utf-8")
        assert "# Judge Validation Report" in content
        assert "Macro F1" in content
        assert "Macro Accuracy" in content

    def test_report_contains_dimension_table(self, tmp_path: Path):
        rows = [_default_row("item-1")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        content = report_md.read_text(encoding="utf-8")
        assert "| Dimension |" in content
        for dim in _DIMS:
            assert dim in content

    def test_metrics_perfect_agreement(self, tmp_path: Path):
        # Human: Yes/Encouraging (all True), Judge: all True → 100% agreement
        rows = [_default_row("item-1"), _default_row("item-2")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        metrics = validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        assert metrics["macro_f1"] == pytest.approx(100.0)
        assert metrics["macro_accuracy"] == pytest.approx(100.0)

    def test_returns_metrics_dict_with_expected_keys(self, tmp_path: Path):
        rows = [_default_row("item-1")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        metrics = validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        assert "macro_f1" in metrics
        assert "macro_accuracy" in metrics
        assert "per_dimension" in metrics
        assert set(metrics["per_dimension"].keys()) == set(_DIMS)  # type: ignore[arg-type]

    def test_judge_reasons_preserved_in_jsonl(self, tmp_path: Path):
        rows = [_default_row("item-1")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        mock_eval = MRBenchEvaluation(**{
            dim: {"reason": f"Reason for {dim}.", "passed": True}
            for dim in _DIMS
        })
        mock_judge = MagicMock()
        mock_judge.evaluate_response.return_value = mock_eval

        validate_judge(input_csv, output_jsonl, report_md, judge=mock_judge)

        record = json.loads(output_jsonl.read_text(encoding="utf-8").splitlines()[0])
        for dim in _DIMS:
            assert record["judge_reasons"][dim] == f"Reason for {dim}."

    def test_disagreement_examples_appear_in_report(self, tmp_path: Path):
        # Human: all True (Yes/Encouraging), Judge: mistake_identification=False → disagreement
        rows = [
            _default_row("item-A"),
            _default_row("item-B"),
        ]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        judge = self._make_judge(mistake_identification=False)
        validate_judge(input_csv, output_jsonl, report_md, judge=judge)

        content = report_md.read_text(encoding="utf-8")
        assert "item-A" in content or "item-B" in content

    def test_unknown_human_label_raises_value_error(self, tmp_path: Path):
        bad_row = _default_row("item-bad")
        bad_row["human_mistake_identification"] = "maybe"

        input_csv = _make_csv(tmp_path, [bad_row])
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        with pytest.raises(ValueError):
            validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

    def test_invalid_tutor_tone_raises_value_error(self, tmp_path: Path):
        # Offensive must be filtered before validate_judge is called
        bad_row = _default_row("item-bad")
        bad_row["human_tutor_tone"] = "Offensive"

        input_csv = _make_csv(tmp_path, [bad_row])
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        with pytest.raises(ValueError, match="Offensive"):
            validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

    def test_tutor_tone_encouraging_maps_to_true(self, tmp_path: Path):
        rows = [_default_row("item-1", human_values={"tutor_tone": "Encouraging"})]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        record = json.loads(output_jsonl.read_text(encoding="utf-8").splitlines()[0])
        assert record["human_labels"]["tutor_tone"] is True

    def test_tutor_tone_neutral_maps_to_false(self, tmp_path: Path):
        rows = [_default_row("item-1", human_values={"tutor_tone": "Neutral"})]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        # Judge returns tutor_tone=True (Encouraging); human=Neutral=False → mismatch
        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        record = json.loads(output_jsonl.read_text(encoding="utf-8").splitlines()[0])
        assert record["human_labels"]["tutor_tone"] is False
        assert record["matches"]["tutor_tone"] is False

    def test_instantiates_judge_when_none(self, tmp_path: Path):
        rows = [_default_row("item-1")]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        evaluation = _make_evaluation()
        with patch("claude_behavior_eval.validate_judge.ClaudeRubricJudge") as MockJudge:
            MockJudge.return_value.evaluate_response.return_value = evaluation
            validate_judge(input_csv, output_jsonl, report_md, judge=None)
            MockJudge.assert_called_once()

    def test_matches_reflect_agreement(self, tmp_path: Path):
        # Human: mistake_identification=No (False), judge=True → mismatch; all others match
        rows = [_default_row("item-1", human_values={"mistake_identification": "No"})]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        record = json.loads(output_jsonl.read_text(encoding="utf-8").splitlines()[0])
        assert record["matches"]["mistake_identification"] is False
        for dim in _DIMS:
            if dim != "mistake_identification":
                assert record["matches"][dim] is True

    def test_tutor_response_excerpt_truncated(self, tmp_path: Path):
        long_response = "A" * 300
        rows = [_default_row("item-1", tutor_response=long_response)]
        input_csv = _make_csv(tmp_path, rows)
        output_jsonl = tmp_path / "results.jsonl"
        report_md = tmp_path / "report.md"

        validate_judge(input_csv, output_jsonl, report_md, judge=self._make_judge())

        record = json.loads(output_jsonl.read_text(encoding="utf-8").splitlines()[0])
        assert len(record["tutor_response_excerpt"]) == 120
