from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from claude_behavior_eval.prepare_mrbench import _CSV_FIELDNAMES, prepare_mrbench_csvs

_FAKE_ITEMS = [
    {
        "conversation_id": "conv-001",
        "conversation_history": "Tutor: What is two plus two?\nStudent: It is five.",
        "Data": "FakeMath",
        "Topic": "Not Available",
        "Ground_Truth_Solution": "GOLD_ANSWER_ALPHA: two plus two equals four",
        "anno_llm_responses": {},
    },
    {
        "conversation_id": "conv-002",
        "conversation_history": "Tutor: Solve x plus three equals seven.\nStudent: x equals three.",
        "Data": "FakeMath",
        "Topic": "Algebra.Linear",
        "Ground_Truth_Solution": "GOLD_ANSWER_BETA: x equals four",
        "anno_llm_responses": {},
    },
    {
        "conversation_id": "conv-003",
        "conversation_history": "Tutor: What is ten divided by two?\nStudent: It is six.",
        "Data": "FakeMath",
        "Topic": "Not Available",
        "Ground_Truth_Solution": "GOLD_ANSWER_GAMMA: ten divided by two equals five",
        "anno_llm_responses": {},
    },
    {
        "conversation_id": "conv-004",
        "conversation_history": "Tutor: Is seventeen a prime number?\nStudent: No.",
        "Data": "FakeMath",
        "Topic": "Number Theory",
        "Ground_Truth_Solution": "GOLD_ANSWER_DELTA: seventeen is indeed prime",
        "anno_llm_responses": {},
    },
    {
        "conversation_id": "conv-005",
        "conversation_history": "Tutor: What is the square root of nine?\nStudent: It is six.",
        "Data": "FakeMath",
        "Topic": "Not Available",
        "Ground_Truth_Solution": "GOLD_ANSWER_EPSILON: the square root of nine is three",
        "anno_llm_responses": {},
    },
]


@pytest.fixture()
def fake_json(tmp_path: Path) -> Path:
    path = tmp_path / "fake_mrbench.json"
    path.write_text(json.dumps(_FAKE_ITEMS), encoding="utf-8")
    return path


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "processed"


class TestOutputFilesCreated:
    def test_dev_csv_is_created(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        assert (output_dir / "dev.csv").exists()

    def test_test_csv_is_created(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        assert (output_dir / "test.csv").exists()

    def test_split_metadata_json_is_created(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        assert (output_dir / "split_metadata.json").exists()

    def test_output_dir_is_created_if_missing(self, fake_json: Path, tmp_path: Path):
        out = tmp_path / "nested" / "deep" / "processed"
        prepare_mrbench_csvs(fake_json, out)
        assert out.exists()


class TestCSVStructure:
    def _read_csv(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_dev_headers_match_dataset_item(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        with (output_dir / "dev.csv").open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == _CSV_FIELDNAMES

    def test_test_headers_match_dataset_item(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        with (output_dir / "test.csv").open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == _CSV_FIELDNAMES

    def test_dev_plus_test_equals_total(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir, dev_ratio=0.6)
        dev = self._read_csv(output_dir / "dev.csv")
        test = self._read_csv(output_dir / "test.csv")
        assert len(dev) + len(test) == len(_FAKE_ITEMS)

    def test_instruction_constraints_is_valid_json_list(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        for row in self._read_csv(output_dir / "dev.csv"):
            parsed = json.loads(row["instruction_constraints"])
            assert isinstance(parsed, list)

    def test_expected_rubric_is_valid_json_dict(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        for row in self._read_csv(output_dir / "dev.csv"):
            parsed = json.loads(row["expected_rubric"])
            assert isinstance(parsed, dict)

    def test_expected_rubric_contains_all_eight_dimensions(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        expected_dims = {
            "mistake_identification", "mistake_location", "answer_revealing_appropriate",
            "providing_guidance", "actionability", "coherence", "tutor_tone", "human_likeness",
        }
        rows = self._read_csv(output_dir / "dev.csv") + self._read_csv(output_dir / "test.csv")
        for row in rows:
            rubric = json.loads(row["expected_rubric"])
            assert set(rubric.keys()) == expected_dims

    def test_expected_rubric_excludes_gold_labels(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        rows = self._read_csv(output_dir / "dev.csv") + self._read_csv(output_dir / "test.csv")
        for row in rows:
            rubric_str = row["expected_rubric"]
            # Gold label values from MRBench annotations must not appear
            for gold_value in ("Yes", "No", "Encouraging", "Neutral"):
                assert gold_value not in rubric_str, (
                    f"Gold label '{gold_value}' found in expected_rubric"
                )

    def test_student_question_not_empty(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        rows = self._read_csv(output_dir / "dev.csv") + self._read_csv(output_dir / "test.csv")
        for row in rows:
            assert row["student_question"].strip() != ""

    def test_ground_truth_not_in_student_question(self, fake_json: Path, output_dir: Path):
        # Gold solutions must not leak into the student_question field
        prepare_mrbench_csvs(fake_json, output_dir)
        rows = self._read_csv(output_dir / "dev.csv") + self._read_csv(output_dir / "test.csv")
        gold_solutions = {item["Ground_Truth_Solution"] for item in _FAKE_ITEMS}
        for row in rows:
            for sol in gold_solutions:
                assert sol not in row["student_question"], (
                    f"Gold solution leaked into student_question: {sol!r}"
                )


class TestSplitBehavior:
    def test_split_is_deterministic_with_same_seed(self, fake_json: Path, tmp_path: Path):
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        prepare_mrbench_csvs(fake_json, out1, seed=99)
        prepare_mrbench_csvs(fake_json, out2, seed=99)
        dev1 = (out1 / "dev.csv").read_text(encoding="utf-8")
        dev2 = (out2 / "dev.csv").read_text(encoding="utf-8")
        assert dev1 == dev2

    def test_different_seeds_produce_different_splits(self, fake_json: Path, tmp_path: Path):
        out1 = tmp_path / "seed1"
        out2 = tmp_path / "seed2"
        prepare_mrbench_csvs(fake_json, out1, seed=1)
        prepare_mrbench_csvs(fake_json, out2, seed=2)
        ids1 = [(r["id"]) for r in _read_csv(out1 / "dev.csv")]
        ids2 = [(r["id"]) for r in _read_csv(out2 / "dev.csv")]
        assert ids1 != ids2

    def test_split_metadata_values_are_correct(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir, dev_ratio=0.6, seed=7)
        with (output_dir / "split_metadata.json").open(encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["total_rows"] == len(_FAKE_ITEMS)
        assert meta["dev_rows"] + meta["test_rows"] == meta["total_rows"]
        assert meta["dev_ratio"] == 0.6
        assert meta["seed"] == 7

    def test_metadata_input_json_is_recorded(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        with (output_dir / "split_metadata.json").open(encoding="utf-8") as f:
            meta = json.load(f)
        assert str(fake_json) == meta["input_json"]


class TestDeduplication:
    def test_duplicate_ids_are_deduplicated(self, tmp_path: Path):
        items_with_dup = _FAKE_ITEMS + [
            {
                "conversation_id": "conv-001",  # duplicate
                "conversation_history": "Same history as conv-001 but different.",
                "Data": "FakeMath",
                "Topic": "Not Available",
                "Ground_Truth_Solution": "...",
                "anno_llm_responses": {},
            }
        ]
        path = tmp_path / "dup.json"
        path.write_text(json.dumps(items_with_dup), encoding="utf-8")
        out = tmp_path / "out"
        prepare_mrbench_csvs(path, out)
        with (out / "split_metadata.json").open(encoding="utf-8") as f:
            meta = json.load(f)
        # 6 input items but only 5 unique conversation_ids
        assert meta["total_rows"] == len(_FAKE_ITEMS)

    def test_missing_conversation_id_gets_stable_synthetic_id(self, tmp_path: Path):
        items = [
            {
                "conversation_history": "Tutor: Q? Student: A.",
                "Data": "FakeMath",
                "Topic": "Not Available",
                "Ground_Truth_Solution": "x",
                "anno_llm_responses": {},
            }
        ]
        path = tmp_path / "noid.json"
        path.write_text(json.dumps(items), encoding="utf-8")
        out = tmp_path / "out"
        prepare_mrbench_csvs(path, out)
        with (out / "dev.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        all_rows = rows
        with (out / "test.csv").open(encoding="utf-8", newline="") as f:
            all_rows += list(csv.DictReader(f))
        ids = [r["id"] for r in all_rows]
        assert all(i.startswith("mrbench_") for i in ids)


class TestTargetLearnerLevel:
    def _all_rows(self, output_dir: Path) -> list[dict]:
        rows = []
        for fname in ("dev.csv", "test.csv"):
            with (output_dir / fname).open(encoding="utf-8", newline="") as f:
                rows.extend(csv.DictReader(f))
        return rows

    def test_informative_topic_used_as_level(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        rows = self._all_rows(output_dir)
        row = next(r for r in rows if r["id"] == "conv-002")
        assert row["target_learner_level"] == "Algebra.Linear"

    def test_not_available_topic_defaults_to_math_student(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        rows = self._all_rows(output_dir)
        row = next(r for r in rows if r["id"] == "conv-001")
        assert row["target_learner_level"] == "math_student"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
