from __future__ import annotations

import csv
from pathlib import Path

import pytest

from claude_behavior_eval.dataset import CSVDatasetLoader
from claude_behavior_eval.schemas import DatasetItem

HEADER = ["id", "student_question", "target_learner_level", "instruction_constraints", "expected_rubric"]


def write_csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture()
def standard_csv(tmp_path: Path) -> Path:
    return write_csv(
        tmp_path / "dataset.csv",
        [
            {
                "id": "item-001",
                "student_question": "Why does x^2 + 1 have no real roots?",
                "target_learner_level": "high_school",
                "instruction_constraints": '["no direct answer", "use Socratic method"]',
                "expected_rubric": '{"coherence": "needs to be logical"}',
            },
            {
                "id": "item-002",
                "student_question": "What is the chain rule?",
                "target_learner_level": "undergraduate",
                "instruction_constraints": '["keep it brief"]',
                "expected_rubric": '{"providing_guidance": "should give a hint"}',
            },
        ],
    )


@pytest.fixture()
def empty_json_fields_csv(tmp_path: Path) -> Path:
    return write_csv(
        tmp_path / "empty_fields.csv",
        [
            {
                "id": "item-003",
                "student_question": "What is a derivative?",
                "target_learner_level": "undergraduate",
                "instruction_constraints": "",
                "expected_rubric": "",
            },
        ],
    )


class TestCSVDatasetLoaderSuccess:
    def test_yields_dataset_items(self, standard_csv: Path):
        items = list(CSVDatasetLoader(standard_csv).load())
        assert all(isinstance(item, DatasetItem) for item in items)

    def test_yields_correct_count(self, standard_csv: Path):
        items = list(CSVDatasetLoader(standard_csv).load())
        assert len(items) == 2

    def test_string_fields_parsed_correctly(self, standard_csv: Path):
        item = list(CSVDatasetLoader(standard_csv).load())[0]
        assert item.id == "item-001"
        assert item.student_question == "Why does x^2 + 1 have no real roots?"
        assert item.target_learner_level == "high_school"

    def test_instruction_constraints_is_list_not_string(self, standard_csv: Path):
        item = list(CSVDatasetLoader(standard_csv).load())[0]
        assert isinstance(item.instruction_constraints, list)
        assert item.instruction_constraints == ["no direct answer", "use Socratic method"]

    def test_expected_rubric_is_dict_not_string(self, standard_csv: Path):
        item = list(CSVDatasetLoader(standard_csv).load())[0]
        assert isinstance(item.expected_rubric, dict)
        assert item.expected_rubric == {"coherence": "needs to be logical"}

    def test_second_row_parsed_correctly(self, standard_csv: Path):
        items = list(CSVDatasetLoader(standard_csv).load())
        assert items[1].id == "item-002"
        assert items[1].instruction_constraints == ["keep it brief"]

    def test_accepts_path_object(self, standard_csv: Path):
        items = list(CSVDatasetLoader(standard_csv).load())
        assert len(items) == 2

    def test_accepts_string_filepath(self, standard_csv: Path):
        items = list(CSVDatasetLoader(str(standard_csv)).load())
        assert len(items) == 2


class TestCSVDatasetLoaderEmptyFields:
    def test_empty_constraints_defaults_to_empty_list(self, empty_json_fields_csv: Path):
        item = list(CSVDatasetLoader(empty_json_fields_csv).load())[0]
        assert item.instruction_constraints == []

    def test_empty_rubric_defaults_to_empty_dict(self, empty_json_fields_csv: Path):
        item = list(CSVDatasetLoader(empty_json_fields_csv).load())[0]
        assert item.expected_rubric == {}

    def test_empty_fields_still_yield_dataset_item(self, empty_json_fields_csv: Path):
        item = list(CSVDatasetLoader(empty_json_fields_csv).load())[0]
        assert isinstance(item, DatasetItem)


class TestCSVDatasetLoaderMalformedJSON:
    def test_raises_value_error_on_bad_constraints(self, tmp_path: Path):
        csv_path = write_csv(
            tmp_path / "bad_constraints.csv",
            [
                {
                    "id": "item-bad",
                    "student_question": "Some question?",
                    "target_learner_level": "high_school",
                    "instruction_constraints": "{not valid json]",
                    "expected_rubric": '{"coherence": "ok"}',
                }
            ],
        )
        with pytest.raises(ValueError, match="instruction_constraints"):
            list(CSVDatasetLoader(csv_path).load())

    def test_raises_value_error_on_bad_rubric(self, tmp_path: Path):
        csv_path = write_csv(
            tmp_path / "bad_rubric.csv",
            [
                {
                    "id": "item-bad",
                    "student_question": "Some question?",
                    "target_learner_level": "high_school",
                    "instruction_constraints": '["ok"]',
                    "expected_rubric": "{not valid json]",
                }
            ],
        )
        with pytest.raises(ValueError, match="expected_rubric"):
            list(CSVDatasetLoader(csv_path).load())

    def test_error_message_includes_row_id(self, tmp_path: Path):
        csv_path = write_csv(
            tmp_path / "bad_with_id.csv",
            [
                {
                    "id": "item-xyz",
                    "student_question": "Some question?",
                    "target_learner_level": "high_school",
                    "instruction_constraints": "NOTJSON",
                    "expected_rubric": "",
                }
            ],
        )
        with pytest.raises(ValueError, match="item-xyz"):
            list(CSVDatasetLoader(csv_path).load())
