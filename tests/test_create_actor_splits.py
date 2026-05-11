"""Tests for scripts/04_create_actor_splits.py actor split creation logic."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

# Import the script module without executing main()
_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "04_create_actor_splits.py"
_spec = importlib.util.spec_from_file_location("create_actor_splits", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

create_actor_splits = _mod.create_actor_splits
sample_mini = _mod.sample_mini
build_forbidden_base_ids = _mod.build_forbidden_base_ids
load_actor_pool = _mod.load_actor_pool
ACTOR_FIELDNAMES = _mod.ACTOR_FIELDNAMES
FULL_TRAIN_SIZE = _mod.FULL_TRAIN_SIZE
FULL_TEST_SIZE = _mod.FULL_TEST_SIZE
MINI_TRAIN_SIZE = _mod.MINI_TRAIN_SIZE
MINI_TEST_SIZE = _mod.MINI_TEST_SIZE
SEED = _mod.SEED
MINI_SEED = _mod.MINI_SEED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_actor_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ACTOR_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_judge_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["id"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _make_actor_rows(n: int, prefix: str = "conv") -> list[dict]:
    """Generate n synthetic actor rows with varying question lengths for bucket coverage."""
    rows = []
    for i in range(n):
        # Vary length: short / medium / long in a repeating pattern
        if i % 3 == 0:
            question = f"Short question {i}?"  # <500 chars
        elif i % 3 == 1:
            question = f"Medium question {i}: " + "x" * 600  # ~620 chars
        else:
            question = f"Long question {i}: " + "x" * 1600  # ~1620 chars
        rows.append({
            "id": f"{prefix}{i:04d}",
            "student_question": question,
            "target_learner_level": f"level_{i % 5}",
            "instruction_constraints": "[]",
            "expected_rubric": "{}",
        })
    return rows


def _make_judge_rows(base_ids: list[str], model: str = "Gemini") -> list[dict]:
    return [{"id": f"{b}_{model}"} for b in base_ids]


# ---------------------------------------------------------------------------
# TestCreateActorSplits (full splits, stratified)
# ---------------------------------------------------------------------------

class TestCreateActorSplits:
    """Tests for create_actor_splits() which produces actor_train and actor_test."""

    def _pool(self, n: int = 200) -> list[dict]:
        return _make_actor_rows(n)

    def test_correct_train_size(self):
        train, _ = create_actor_splits(self._pool(), set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        assert len(train) == FULL_TRAIN_SIZE

    def test_correct_test_size(self):
        _, test = create_actor_splits(self._pool(), set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        assert len(test) == FULL_TEST_SIZE

    def test_train_test_disjoint(self):
        train, test = create_actor_splits(self._pool(), set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        assert {r["id"] for r in train}.isdisjoint({r["id"] for r in test})

    def test_no_duplicate_ids_in_train(self):
        train, _ = create_actor_splits(self._pool(), set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        ids = [r["id"] for r in train]
        assert len(ids) == len(set(ids))

    def test_no_duplicate_ids_in_test(self):
        _, test = create_actor_splits(self._pool(), set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        ids = [r["id"] for r in test]
        assert len(ids) == len(set(ids))

    def test_forbidden_ids_excluded_from_train(self):
        rows = self._pool()
        forbidden = {f"conv{i:04d}" for i in range(10)}
        train, _ = create_actor_splits(rows, forbidden, FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        assert not any(r["id"] in forbidden for r in train)

    def test_forbidden_ids_excluded_from_test(self):
        rows = self._pool()
        forbidden = {f"conv{i:04d}" for i in range(10)}
        _, test = create_actor_splits(rows, forbidden, FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        assert not any(r["id"] in forbidden for r in test)

    def test_raises_when_pool_too_small(self):
        rows = _make_actor_rows(90)  # 90 < 80+20=100
        with pytest.raises(ValueError, match="eligible"):
            create_actor_splits(rows, set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)

    def test_raises_when_forbidden_makes_pool_too_small(self):
        rows = _make_actor_rows(110)
        forbidden = {f"conv{i:04d}" for i in range(20)}  # leaves 90, still < 100
        with pytest.raises(ValueError, match="eligible"):
            create_actor_splits(rows, forbidden, FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)

    def test_raises_when_all_rows_forbidden(self):
        rows = self._pool()
        forbidden = {r["id"] for r in rows}
        with pytest.raises(ValueError, match="eligible"):
            create_actor_splits(rows, forbidden, FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)

    def test_deterministic_with_same_seed(self):
        rows = self._pool()
        train_a, test_a = create_actor_splits(rows, set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=10)
        train_b, test_b = create_actor_splits(rows, set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=10)
        assert [r["id"] for r in train_a] == [r["id"] for r in train_b]
        assert [r["id"] for r in test_a] == [r["id"] for r in test_b]

    def test_different_seeds_usually_give_different_splits(self):
        rows = self._pool()
        train_a, _ = create_actor_splits(rows, set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, 42, max_attempts=1)
        train_b, _ = create_actor_splits(rows, set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, 99, max_attempts=1)
        assert [r["id"] for r in train_a] != [r["id"] for r in train_b]


# ---------------------------------------------------------------------------
# TestSampleMini
# ---------------------------------------------------------------------------

class TestSampleMini:
    """Tests for sample_mini() which subsamples actor_train → actor_mini_train."""

    def test_correct_size(self):
        rows = _make_actor_rows(80)
        result = sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)
        assert len(result) == MINI_TRAIN_SIZE

    def test_result_is_subset_of_source(self):
        rows = _make_actor_rows(80)
        result = sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)
        source_ids = {r["id"] for r in rows}
        assert all(r["id"] in source_ids for r in result)

    def test_no_duplicates_in_result(self):
        rows = _make_actor_rows(80)
        result = sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)
        ids = [r["id"] for r in result]
        assert len(ids) == len(set(ids))

    def test_equal_size_returns_copy_unchanged(self):
        rows = _make_actor_rows(MINI_TRAIN_SIZE)
        result = sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)
        assert len(result) == MINI_TRAIN_SIZE
        assert {r["id"] for r in result} == {r["id"] for r in rows}

    def test_returns_new_list_not_same_object(self):
        rows = _make_actor_rows(MINI_TRAIN_SIZE)
        result = sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)
        assert result is not rows

    def test_deterministic(self):
        rows = _make_actor_rows(80)
        a = sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)
        b = sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)
        assert [r["id"] for r in a] == [r["id"] for r in b]

    def test_raises_when_source_too_small(self):
        rows = _make_actor_rows(10)
        with pytest.raises(ValueError, match="sample"):
            sample_mini(rows, MINI_TRAIN_SIZE, MINI_SEED)

    def test_mini_test_equals_full_test_when_sizes_match(self):
        # MINI_TEST_SIZE == FULL_TEST_SIZE == 20; sample_mini should return all rows
        rows = _make_actor_rows(FULL_TEST_SIZE)
        result = sample_mini(rows, MINI_TEST_SIZE, MINI_SEED)
        assert len(result) == FULL_TEST_SIZE
        assert {r["id"] for r in result} == {r["id"] for r in rows}


# ---------------------------------------------------------------------------
# TestMiniSubsets (relationship between full and mini splits)
# ---------------------------------------------------------------------------

class TestMiniSubsets:
    """Verify that mini splits are strict subsets of the corresponding full splits."""

    def _make_splits(self) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        rows = _make_actor_rows(200)
        train, test = create_actor_splits(rows, set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        mini_train = sample_mini(train, MINI_TRAIN_SIZE, MINI_SEED)
        mini_test = sample_mini(test, MINI_TEST_SIZE, MINI_SEED)
        return train, test, mini_train, mini_test

    def test_mini_train_is_subset_of_full_train(self):
        train, _, mini_train, _ = self._make_splits()
        train_ids = {r["id"] for r in train}
        assert all(r["id"] in train_ids for r in mini_train)

    def test_mini_test_is_subset_of_full_test(self):
        _, test, _, mini_test = self._make_splits()
        test_ids = {r["id"] for r in test}
        assert all(r["id"] in test_ids for r in mini_test)

    def test_mini_train_not_in_test(self):
        _, test, mini_train, _ = self._make_splits()
        test_ids = {r["id"] for r in test}
        assert not any(r["id"] in test_ids for r in mini_train)

    def test_mini_test_not_in_train(self):
        train, _, _, mini_test = self._make_splits()
        train_ids = {r["id"] for r in train}
        assert not any(r["id"] in train_ids for r in mini_test)

    def test_mini_train_correct_size(self):
        _, _, mini_train, _ = self._make_splits()
        assert len(mini_train) == MINI_TRAIN_SIZE

    def test_mini_test_correct_size(self):
        _, _, _, mini_test = self._make_splits()
        assert len(mini_test) == MINI_TEST_SIZE

    def test_mini_test_equals_full_test(self):
        # Since MINI_TEST_SIZE == FULL_TEST_SIZE, mini_test must be the same set as test
        _, test, _, mini_test = self._make_splits()
        assert {r["id"] for r in mini_test} == {r["id"] for r in test}


# ---------------------------------------------------------------------------
# TestBuildForbiddenBaseIds
# ---------------------------------------------------------------------------

class TestBuildForbiddenBaseIds:
    def test_strips_model_suffix(self, tmp_path: Path):
        judge_csv = _write_judge_csv(
            tmp_path / "judge.csv",
            [{"id": "conv0001_Gemini"}, {"id": "conv0002_Phi3"}],
        )
        assert build_forbidden_base_ids([judge_csv]) == {"conv0001", "conv0002"}

    def test_multiple_models_same_conv_deduped(self, tmp_path: Path):
        judge_csv = _write_judge_csv(
            tmp_path / "judge.csv",
            [{"id": "conv0001_Gemini"}, {"id": "conv0001_Phi3"}],
        )
        assert build_forbidden_base_ids([judge_csv]) == {"conv0001"}

    def test_multiple_files_unioned(self, tmp_path: Path):
        j1 = _write_judge_csv(tmp_path / "j1.csv", [{"id": "conv0001_Gemini"}])
        j2 = _write_judge_csv(tmp_path / "j2.csv", [{"id": "conv0002_Phi3"}])
        assert build_forbidden_base_ids([j1, j2]) == {"conv0001", "conv0002"}

    def test_missing_file_warns_but_does_not_crash(self, tmp_path: Path, capsys):
        result = build_forbidden_base_ids([tmp_path / "nonexistent.csv"])
        assert result == set()
        assert "WARNING" in capsys.readouterr().out

    def test_empty_file_returns_empty_set(self, tmp_path: Path):
        judge_csv = _write_judge_csv(tmp_path / "empty.csv", [])
        assert build_forbidden_base_ids([judge_csv]) == set()


# ---------------------------------------------------------------------------
# TestLoadActorPool
# ---------------------------------------------------------------------------

class TestLoadActorPool:
    def test_loads_rows_from_single_file(self, tmp_path: Path):
        p = _write_actor_csv(tmp_path / "dev.csv", _make_actor_rows(5))
        assert len(load_actor_pool([p])) == 5

    def test_concatenates_multiple_files(self, tmp_path: Path):
        p1 = _write_actor_csv(tmp_path / "dev.csv", _make_actor_rows(5, "a"))
        p2 = _write_actor_csv(tmp_path / "test.csv", _make_actor_rows(3, "b"))
        assert len(load_actor_pool([p1, p2])) == 8

    def test_deduplicates_same_id_across_files(self, tmp_path: Path, capsys):
        rows = _make_actor_rows(3, "conv")
        p1 = _write_actor_csv(tmp_path / "dev.csv", rows)
        p2 = _write_actor_csv(tmp_path / "test.csv", rows)  # same IDs
        result = load_actor_pool([p1, p2])
        assert len(result) == 3
        assert "duplicate" in capsys.readouterr().out.lower()

    def test_exits_on_missing_file(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            load_actor_pool([tmp_path / "missing.csv"])


# ---------------------------------------------------------------------------
# TestOutputColumns
# ---------------------------------------------------------------------------

class TestOutputColumns:
    def test_actor_fieldnames_excludes_human_labels(self):
        assert "tutor_response" not in ACTOR_FIELDNAMES
        assert "human_coherence" not in ACTOR_FIELDNAMES
        assert "human_tutor_tone" not in ACTOR_FIELDNAMES

    def test_actor_fieldnames_has_exactly_five_columns(self):
        assert len(ACTOR_FIELDNAMES) == 5

    def test_actor_fieldnames_correct_set(self):
        assert set(ACTOR_FIELDNAMES) == {
            "id", "student_question", "target_learner_level",
            "instruction_constraints", "expected_rubric",
        }

    def test_write_ignores_extra_columns(self, tmp_path: Path):
        rows = _make_actor_rows(FULL_TRAIN_SIZE + FULL_TEST_SIZE)
        for r in rows:
            r["tutor_response"] = "secret"
            r["human_coherence"] = "Yes"
        train, _ = create_actor_splits(rows, set(), FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        path = tmp_path / "out.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ACTOR_FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(train)
        readback = list(csv.DictReader(path.open()))
        assert "tutor_response" not in readback[0]
        assert "human_coherence" not in readback[0]


# ---------------------------------------------------------------------------
# TestConstantValues
# ---------------------------------------------------------------------------

class TestConstantValues:
    def test_full_train_size(self):
        assert FULL_TRAIN_SIZE == 80

    def test_full_test_size(self):
        assert FULL_TEST_SIZE == 20

    def test_mini_train_size(self):
        assert MINI_TRAIN_SIZE == 30

    def test_mini_test_size(self):
        assert MINI_TEST_SIZE == 20

    def test_mini_test_equals_full_test_size(self):
        # actor_mini_test = actor_test exactly (no resampling needed)
        assert MINI_TEST_SIZE == FULL_TEST_SIZE

    def test_seed(self):
        assert SEED == 42

    def test_mini_seed_differs_from_seed(self):
        assert MINI_SEED != SEED


# ---------------------------------------------------------------------------
# TestEndToEnd (integration: write files, read back)
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_full_pipeline_produces_all_four_files(self, tmp_path: Path):
        pool_rows = _make_actor_rows(200, "conv")
        judge_rows = _make_judge_rows([f"conv{i:04d}" for i in range(5)])
        judge_csv = _write_judge_csv(tmp_path / "judge_dev.csv", judge_rows)

        forbidden = build_forbidden_base_ids([judge_csv])
        train, test = create_actor_splits(pool_rows, forbidden, FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        mini_train = sample_mini(train, MINI_TRAIN_SIZE, MINI_SEED)
        mini_test = sample_mini(test, MINI_TEST_SIZE, MINI_SEED)

        out = {}
        for name, rows in [
            ("actor_train", train), ("actor_test", test),
            ("actor_mini_train", mini_train), ("actor_mini_test", mini_test),
        ]:
            path = tmp_path / f"{name}.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=ACTOR_FIELDNAMES, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            out[name] = list(csv.DictReader(path.open()))

        assert len(out["actor_train"]) == FULL_TRAIN_SIZE
        assert len(out["actor_test"]) == FULL_TEST_SIZE
        assert len(out["actor_mini_train"]) == MINI_TRAIN_SIZE
        assert len(out["actor_mini_test"]) == MINI_TEST_SIZE

        train_ids = {r["id"] for r in out["actor_train"]}
        test_ids = {r["id"] for r in out["actor_test"]}
        mini_train_ids = {r["id"] for r in out["actor_mini_train"]}
        mini_test_ids = {r["id"] for r in out["actor_mini_test"]}

        assert train_ids.isdisjoint(test_ids)
        assert mini_train_ids <= train_ids
        assert mini_test_ids <= test_ids

        assert set(out["actor_train"][0].keys()) == set(ACTOR_FIELDNAMES)
        assert not any(r["id"] in forbidden for r in out["actor_train"] + out["actor_test"])

    def test_forbidden_ids_absent_from_all_outputs(self, tmp_path: Path):
        pool_rows = _make_actor_rows(200, "conv")
        forbidden = {f"conv{i:04d}" for i in range(20)}

        train, test = create_actor_splits(pool_rows, forbidden, FULL_TRAIN_SIZE, FULL_TEST_SIZE, SEED, max_attempts=1)
        mini_train = sample_mini(train, MINI_TRAIN_SIZE, MINI_SEED)
        mini_test = sample_mini(test, MINI_TEST_SIZE, MINI_SEED)

        for split in [train, test, mini_train, mini_test]:
            assert not any(r["id"] in forbidden for r in split)
