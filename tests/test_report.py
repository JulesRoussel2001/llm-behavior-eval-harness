from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from claude_behavior_eval.report import _METRIC_ORDER, generate_markdown_report, main

# Dummy metrics matching the output shape of calculate_metrics
_BASELINE: dict[str, float] = {
    "deterministic_pass_rate": 75.0,
    "mistake_identification_pass_rate": 60.0,
    "mistake_location_pass_rate": 50.0,
    "answer_revealing_appropriate_pass_rate": 80.0,
    "providing_guidance_pass_rate": 70.0,
    "actionability_pass_rate": 65.0,
    "coherence_pass_rate": 85.0,
    "tutor_tone_pass_rate": 90.0,
    "human_likeness_pass_rate": 55.0,
    "judge_macro_pass_rate": 69.4,
}

_OPTIMIZED: dict[str, float] = {
    "deterministic_pass_rate": 90.0,
    "mistake_identification_pass_rate": 75.0,
    "mistake_location_pass_rate": 40.0,   # lower than baseline → negative delta
    "answer_revealing_appropriate_pass_rate": 80.0,   # equal → +0.0
    "providing_guidance_pass_rate": 85.0,
    "actionability_pass_rate": 70.0,
    "coherence_pass_rate": 95.0,
    "tutor_tone_pass_rate": 100.0,
    "human_likeness_pass_rate": 60.0,
    "judge_macro_pass_rate": 75.6,
}


class TestGenerateMarkdownReportStructure:
    def setup_method(self):
        self.report = generate_markdown_report(_BASELINE, _OPTIMIZED)
        self.lines = self.report.strip().splitlines()

    def test_first_line_is_header(self):
        assert self.lines[0] == "| Metric | Baseline | Optimized | Delta (pts) |"

    def test_second_line_is_separator(self):
        assert self.lines[1] == "|---|---|---|---|"

    def test_total_row_count(self):
        # header + separator + 10 metric rows
        assert len(self.lines) == 12

    def test_all_metrics_present_in_order(self):
        row_metrics = [line.split("|")[1].strip() for line in self.lines[2:]]
        assert row_metrics == _METRIC_ORDER

    def test_report_ends_with_newline(self):
        assert self.report.endswith("\n")

    def test_baseline_values_formatted_as_percentage(self):
        det_row = self.lines[2]
        assert "75.0%" in det_row

    def test_optimized_values_formatted_as_percentage(self):
        det_row = self.lines[2]
        assert "90.0%" in det_row


class TestGenerateMarkdownReportDeltas:
    def setup_method(self):
        self.report = generate_markdown_report(_BASELINE, _OPTIMIZED)
        self.lines = self.report.strip().splitlines()

    def _row_for(self, metric: str) -> str:
        for line in self.lines[2:]:
            if line.split("|")[1].strip() == metric:
                return line
        raise KeyError(metric)

    def test_positive_delta_has_plus_sign(self):
        row = self._row_for("deterministic_pass_rate")
        delta_cell = row.split("|")[4].strip()
        assert delta_cell == "+15.0"

    def test_negative_delta_has_minus_sign(self):
        row = self._row_for("mistake_location_pass_rate")
        delta_cell = row.split("|")[4].strip()
        assert delta_cell == "-10.0"

    def test_zero_delta_has_plus_sign(self):
        row = self._row_for("answer_revealing_appropriate_pass_rate")
        delta_cell = row.split("|")[4].strip()
        assert delta_cell == "+0.0"

    def test_delta_is_one_decimal_place(self):
        row = self._row_for("judge_macro_pass_rate")
        delta_cell = row.split("|")[4].strip()
        assert "." in delta_cell
        assert len(delta_cell.split(".")[1]) == 1


class TestGenerateMarkdownReportErrors:
    def test_raises_value_error_for_missing_baseline_metric(self):
        incomplete = {k: v for k, v in _BASELINE.items() if k != "coherence_pass_rate"}
        with pytest.raises(ValueError, match="coherence_pass_rate"):
            generate_markdown_report(incomplete, _OPTIMIZED)

    def test_raises_value_error_for_missing_optimized_metric(self):
        incomplete = {k: v for k, v in _OPTIMIZED.items() if k != "judge_macro_pass_rate"}
        with pytest.raises(ValueError, match="judge_macro_pass_rate"):
            generate_markdown_report(_BASELINE, incomplete)

    def test_error_message_names_the_missing_metric(self):
        incomplete = {k: v for k, v in _BASELINE.items() if k != "actionability_pass_rate"}
        with pytest.raises(ValueError, match="actionability_pass_rate"):
            generate_markdown_report(incomplete, _OPTIMIZED)

    def test_raises_on_empty_baseline(self):
        with pytest.raises(ValueError):
            generate_markdown_report({}, _OPTIMIZED)


class TestMainCLI:
    def test_writes_report_to_output_md(self, tmp_path: Path, monkeypatch):
        output_path = tmp_path / "report.md"
        monkeypatch.setattr("sys.argv", [
            "report.py",
            "--baseline-jsonl", "fake_baseline.jsonl",
            "--optimized-jsonl", "fake_optimized.jsonl",
            "--output-md", str(output_path),
        ])
        with patch("claude_behavior_eval.report.calculate_metrics", side_effect=[_BASELINE, _OPTIMIZED]):
            main()
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "| Metric | Baseline | Optimized | Delta (pts) |" in content

    def test_creates_output_parent_directory(self, tmp_path: Path, monkeypatch):
        output_path = tmp_path / "nested" / "deep" / "report.md"
        monkeypatch.setattr("sys.argv", [
            "report.py",
            "--baseline-jsonl", "fake_baseline.jsonl",
            "--optimized-jsonl", "fake_optimized.jsonl",
            "--output-md", str(output_path),
        ])
        with patch("claude_behavior_eval.report.calculate_metrics", side_effect=[_BASELINE, _OPTIMIZED]):
            main()
        assert output_path.exists()

    def test_prints_to_stdout_when_no_output_md(self, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", [
            "report.py",
            "--baseline-jsonl", "fake_baseline.jsonl",
            "--optimized-jsonl", "fake_optimized.jsonl",
        ])
        with patch("claude_behavior_eval.report.calculate_metrics", side_effect=[_BASELINE, _OPTIMIZED]):
            main()
        captured = capsys.readouterr()
        assert "| Metric |" in captured.out
        assert "deterministic_pass_rate" in captured.out
