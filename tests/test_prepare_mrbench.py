from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from claude_behavior_eval.prepare_mrbench import (
    _CSV_FIELDNAMES,
    _VALIDATION_FIELDNAMES,
    prepare_mrbench_csvs,
)

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


# ---------------------------------------------------------------------------
# Fixtures and data for judge_validation_raw.csv tests
# ---------------------------------------------------------------------------

_FAKE_ITEMS_WITH_RESPONSES = [
    {
        "conversation_id": "conv-vld-001",
        "conversation_history": "Tutor: What is two plus two?\nStudent: It is five.",
        "Data": "FakeMath",
        "Topic": "Arithmetic",
        "Ground_Truth_Solution": "GOLD: two plus two equals four",
        "anno_llm_responses": {
            "ModelA": {
                "response": "Good try! The answer is actually four, not five.",
                "annotation": {
                    "Mistake_Identification": "Yes",
                    "Mistake_Location": "Yes",
                    "Revealing_of_the_Answer": "Yes",   # inverted → "No"
                    "Providing_Guidance": "Yes",
                    "Actionability": "Yes",
                    "Coherence": "Yes",
                    "Tutor_Tone": "Encouraging",         # not Yes/No → ""
                    "humanlikeness": "Yes",
                },
            },
            "ModelB": {
                "response": "Think about what comes after three.",
                "annotation": {
                    "Mistake_Identification": "Yes",
                    "Mistake_Location": "No",
                    "Revealing_of_the_Answer": "No",     # inverted → "Yes"
                    "Providing_Guidance": "Yes",
                    "Actionability": "No",
                    "Coherence": "Yes",
                    "Tutor_Tone": "Neutral",             # not Yes/No → ""
                    "humanlikeness": "Yes",
                },
            },
        },
    },
    {
        "conversation_id": "conv-vld-002",
        "conversation_history": "Tutor: Solve x+3=7.\nStudent: x equals three.",
        "Data": "FakeMath",
        "Topic": "Not Available",
        "Ground_Truth_Solution": "GOLD: x equals four",
        "anno_llm_responses": {},   # no responses → no validation rows
    },
]


@pytest.fixture()
def fake_json_with_responses(tmp_path: Path) -> Path:
    path = tmp_path / "fake_mrbench_responses.json"
    path.write_text(json.dumps(_FAKE_ITEMS_WITH_RESPONSES), encoding="utf-8")
    return path


@pytest.fixture()
def output_dir_vld(tmp_path: Path) -> Path:
    return tmp_path / "processed_vld"


class TestJudgeValidationCSVCreated:
    def test_file_is_created(self, fake_json: Path, output_dir: Path):
        prepare_mrbench_csvs(fake_json, output_dir)
        assert (output_dir / "judge_validation_raw.csv").exists()

    def test_has_required_columns(self, fake_json_with_responses: Path, output_dir_vld: Path):
        prepare_mrbench_csvs(fake_json_with_responses, output_dir_vld)
        with (output_dir_vld / "judge_validation_raw.csv").open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == _VALIDATION_FIELDNAMES

    def test_row_count_matches_model_count(self, fake_json_with_responses: Path, output_dir_vld: Path):
        prepare_mrbench_csvs(fake_json_with_responses, output_dir_vld)
        rows = _read_csv(output_dir_vld / "judge_validation_raw.csv")
        # conv-vld-001 has 2 models, conv-vld-002 has 0 → total 2 rows
        assert len(rows) == 2

    def test_has_nonempty_tutor_response(self, fake_json_with_responses: Path, output_dir_vld: Path):
        prepare_mrbench_csvs(fake_json_with_responses, output_dir_vld)
        rows = _read_csv(output_dir_vld / "judge_validation_raw.csv")
        assert any(r["tutor_response"].strip() for r in rows)

    def test_dev_and_test_still_created(self, fake_json_with_responses: Path, output_dir_vld: Path):
        prepare_mrbench_csvs(fake_json_with_responses, output_dir_vld)
        assert (output_dir_vld / "dev.csv").exists()
        assert (output_dir_vld / "test.csv").exists()

    def test_split_metadata_still_created(self, fake_json_with_responses: Path, output_dir_vld: Path):
        prepare_mrbench_csvs(fake_json_with_responses, output_dir_vld)
        assert (output_dir_vld / "split_metadata.json").exists()


class TestJudgeValidationCSVLabels:
    def _get_row(self, rows: list[dict], model_suffix: str) -> dict:
        for r in rows:
            if r["id"].endswith(f"_{model_suffix}"):
                return r
        raise KeyError(model_suffix)

    def _rows(self, fake_json_with_responses: Path, output_dir_vld: Path) -> list[dict]:
        prepare_mrbench_csvs(fake_json_with_responses, output_dir_vld)
        return _read_csv(output_dir_vld / "judge_validation_raw.csv")

    def test_answer_revealing_yes_inverted_to_no(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        row = self._get_row(rows, "ModelA")
        # MRBench "Yes" (revealed answer) → human_answer_revealing_appropriate = "No"
        assert row["human_answer_revealing_appropriate"] == "No"

    def test_answer_revealing_no_inverted_to_yes(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        row = self._get_row(rows, "ModelB")
        # MRBench "No" (did not reveal answer) → human_answer_revealing_appropriate = "Yes"
        assert row["human_answer_revealing_appropriate"] == "Yes"

    def test_tutor_tone_stored_categorically(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        # Tutor_Tone is stored as-is (Encouraging/Neutral/Offensive), not mapped to Yes/No
        row_a = self._get_row(rows, "ModelA")
        row_b = self._get_row(rows, "ModelB")
        assert row_a["human_tutor_tone"] == "Encouraging"
        assert row_b["human_tutor_tone"] == "Neutral"

    def test_standard_yes_preserved_for_noninverted_dim(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        row = self._get_row(rows, "ModelA")
        assert row["human_mistake_identification"] == "Yes"

    def test_standard_no_preserved_for_noninverted_dim(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        row = self._get_row(rows, "ModelB")
        assert row["human_mistake_location"] == "No"

    def test_row_id_contains_model_name(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        ids = {r["id"] for r in rows}
        assert any("ModelA" in i for i in ids)
        assert any("ModelB" in i for i in ids)

    def test_student_question_matches_conversation_history(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        row = self._get_row(rows, "ModelA")
        assert "two plus two" in row["student_question"]

    def test_target_learner_level_from_topic(
        self, fake_json_with_responses: Path, output_dir_vld: Path
    ):
        rows = self._rows(fake_json_with_responses, output_dir_vld)
        row = self._get_row(rows, "ModelA")
        assert row["target_learner_level"] == "Arithmetic"


# ---------------------------------------------------------------------------
# Tests for qualified "Yes (...)" Revealing_of_the_Answer normalization
# ---------------------------------------------------------------------------

_FAKE_ITEMS_QUALIFIED_REVEALING = [
    {
        "conversation_id": "conv-rev-001",
        "conversation_history": "Tutor: What is 2+2?\nStudent: It is five.",
        "Data": "FakeMath",
        "Topic": "Arithmetic",
        "Ground_Truth_Solution": "GOLD: four",
        "anno_llm_responses": {
            # Plain "No": tutor did NOT reveal → appropriate → "Yes" (after inversion)
            "ModelNo": {
                "response": "Think about it again.",
                "annotation": {
                    "Mistake_Identification": "Yes",
                    "Mistake_Location": "Yes",
                    "Revealing_of_the_Answer": "No",
                    "Providing_Guidance": "Yes",
                    "Actionability": "Yes",
                    "Coherence": "Yes",
                    "Tutor_Tone": "Encouraging",
                    "humanlikeness": "Yes",
                },
            },
            # "Yes (and the answer is correct)": tutor revealed correctly → NOT appropriate → "No"
            "ModelYesCorrect": {
                "response": "The answer is four.",
                "annotation": {
                    "Mistake_Identification": "Yes",
                    "Mistake_Location": "Yes",
                    "Revealing_of_the_Answer": "Yes (and the answer is correct)",
                    "Providing_Guidance": "Yes",
                    "Actionability": "Yes",
                    "Coherence": "Yes",
                    "Tutor_Tone": "Neutral",
                    "humanlikeness": "Yes",
                },
            },
            # "Yes (but the answer is incorrect)": tutor revealed incorrectly → NOT appropriate → "No"
            "ModelYesWrong": {
                "response": "The answer is three.",
                "annotation": {
                    "Mistake_Identification": "No",
                    "Mistake_Location": "No",
                    "Revealing_of_the_Answer": "Yes (but the answer is incorrect)",
                    "Providing_Guidance": "No",
                    "Actionability": "No",
                    "Coherence": "No",
                    "Tutor_Tone": "Neutral",
                    "humanlikeness": "No",
                },
            },
        },
    },
]


@pytest.fixture()
def fake_json_qualified_revealing(tmp_path: Path) -> Path:
    path = tmp_path / "fake_qualified_revealing.json"
    path.write_text(json.dumps(_FAKE_ITEMS_QUALIFIED_REVEALING), encoding="utf-8")
    return path


class TestRevealingAnswerNormalization:
    """Tests for the Revealing_of_the_Answer → human_answer_revealing_appropriate mapping.

    MRBench uses three qualified values for Revealing_of_the_Answer:
      "No"                              → appropriate → "Yes" (after inversion)
      "Yes (and the answer is correct)" → revealed    → "No"  (after inversion)
      "Yes (but the answer is incorrect)"→ revealed   → "No"  (after inversion)

    The previous normalizer only recognized exact "Yes", mapping the two qualified
    forms to empty string. The fix treats any value starting with "Yes" as revealing.
    """

    def _get(self, rows: list[dict], suffix: str) -> dict:
        for r in rows:
            if r["id"].endswith(f"_{suffix}"):
                return r
        raise KeyError(suffix)

    def _rows(self, fake_json_qualified_revealing: Path, tmp_path: Path) -> list[dict]:
        out = tmp_path / "out_rev"
        prepare_mrbench_csvs(fake_json_qualified_revealing, out)
        return _read_csv(out / "judge_validation_raw.csv")

    def test_plain_no_inverted_to_yes(
        self, fake_json_qualified_revealing: Path, tmp_path: Path
    ):
        rows = self._rows(fake_json_qualified_revealing, tmp_path)
        row = self._get(rows, "ModelNo")
        assert row["human_answer_revealing_appropriate"] == "Yes"

    def test_yes_and_correct_inverted_to_no(
        self, fake_json_qualified_revealing: Path, tmp_path: Path
    ):
        # "Yes (and the answer is correct)" means the tutor revealed the answer.
        # Revealing is pedagogically bad → mapped to "No" (not appropriate).
        rows = self._rows(fake_json_qualified_revealing, tmp_path)
        row = self._get(rows, "ModelYesCorrect")
        assert row["human_answer_revealing_appropriate"] == "No"

    def test_yes_but_wrong_inverted_to_no(
        self, fake_json_qualified_revealing: Path, tmp_path: Path
    ):
        # "Yes (but the answer is incorrect)" → still revealing → "No".
        rows = self._rows(fake_json_qualified_revealing, tmp_path)
        row = self._get(rows, "ModelYesWrong")
        assert row["human_answer_revealing_appropriate"] == "No"

    def test_three_rows_generated(
        self, fake_json_qualified_revealing: Path, tmp_path: Path
    ):
        rows = self._rows(fake_json_qualified_revealing, tmp_path)
        assert len(rows) == 3

    def test_tutor_tone_still_categorical(
        self, fake_json_qualified_revealing: Path, tmp_path: Path
    ):
        rows = self._rows(fake_json_qualified_revealing, tmp_path)
        row = self._get(rows, "ModelNo")
        assert row["human_tutor_tone"] == "Encouraging"
        row2 = self._get(rows, "ModelYesCorrect")
        assert row2["human_tutor_tone"] == "Neutral"
