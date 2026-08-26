"""Tests for scripts/04_create_actor_splits.py actor split creation logic.

Actor splits changed to: actor_test = 60 conversations, actor_train = the rest of
the eligible pool capped at 55. Mini splits were removed. Forbidden conversation
ids are read from judge_split_manifest.json.
"""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

# Import the script module without executing main()
_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "04_create_actor_splits.py"
_spec = importlib.util.spec_from_file_location("create_actor_splits", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

create_actor_splits = _mod.create_actor_splits
build_forbidden_base_ids = _mod.build_forbidden_base_ids
load_actor_pool = _mod.load_actor_pool
ACTOR_FIELDNAMES = _mod.ACTOR_FIELDNAMES
FULL_TEST_SIZE = _mod.FULL_TEST_SIZE
FULL_TRAIN_CAP = _mod.FULL_TRAIN_CAP
SEED = _mod.SEED


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


def _write_manifest(path: Path, cal=None, dev=None, test=None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "seed": 42,
        "calibration": {"conversation_ids": cal or []},
        "judge_dev": {"conversation_ids": dev or []},
        "judge_test": {"conversation_ids": test or []},
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _make_actor_rows(n: int, prefix: str = "conv") -> list[dict]:
    """Generate n synthetic actor rows with varying question lengths."""
    rows = []
    for i in range(n):
        if i % 3 == 0:
            question = f"Short question {i}?"
        elif i % 3 == 1:
            question = f"Medium question {i}: " + "x" * 600
        else:
            question = f"Long question {i}: " + "x" * 1600
        rows.append({
            "id": f"{prefix}{i:04d}",
            "student_question": question,
            "target_learner_level": f"level_{i % 5}",
            "instruction_constraints": "[]",
            "expected_rubric": "{}",
        })
    return rows


# ---------------------------------------------------------------------------
# TestCreateActorSplits
# ---------------------------------------------------------------------------

class TestCreateActorSplits:
    def _pool(self, n: int = 200) -> list[dict]:
        return _make_actor_rows(n)

    def test_test_size_is_60(self):
        _, test = create_actor_splits(self._pool(), set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        assert len(test) == FULL_TEST_SIZE

    def test_train_capped_at_55_when_pool_large(self):
        train, _ = create_actor_splits(self._pool(200), set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        assert len(train) == FULL_TRAIN_CAP

    def test_train_is_remainder_when_below_cap(self):
        # 112 eligible → test 60, remainder 52 (< cap 55)
        train, test = create_actor_splits(self._pool(112), set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        assert len(test) == 60
        assert len(train) == 52

    def test_train_test_disjoint(self):
        train, test = create_actor_splits(self._pool(), set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        assert {r["id"] for r in train}.isdisjoint({r["id"] for r in test})

    def test_no_duplicate_ids(self):
        train, test = create_actor_splits(self._pool(), set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        for split in (train, test):
            ids = [r["id"] for r in split]
            assert len(ids) == len(set(ids))

    def test_forbidden_excluded_from_both(self):
        rows = self._pool()
        forbidden = {f"conv{i:04d}" for i in range(10)}
        train, test = create_actor_splits(rows, forbidden, FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        assert not any(r["id"] in forbidden for r in train + test)

    def test_raises_when_pool_too_small(self):
        rows = _make_actor_rows(60)  # eligible 60 == test_size → cannot leave a train row
        with pytest.raises(ValueError, match="eligible"):
            create_actor_splits(rows, set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)

    def test_raises_when_forbidden_makes_pool_too_small(self):
        rows = _make_actor_rows(70)
        forbidden = {f"conv{i:04d}" for i in range(15)}  # leaves 55 < 61
        with pytest.raises(ValueError, match="eligible"):
            create_actor_splits(rows, forbidden, FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)

    def test_deterministic_with_same_seed(self):
        rows = self._pool()
        a_tr, a_te = create_actor_splits(rows, set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        b_tr, b_te = create_actor_splits(rows, set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
        assert [r["id"] for r in a_tr] == [r["id"] for r in b_tr]
        assert [r["id"] for r in a_te] == [r["id"] for r in b_te]

    def test_different_seeds_usually_differ(self):
        rows = self._pool()
        a, _ = create_actor_splits(rows, set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, 42)
        b, _ = create_actor_splits(rows, set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, 99)
        assert [r["id"] for r in a] != [r["id"] for r in b]


# ---------------------------------------------------------------------------
# TestBuildForbiddenBaseIds (manifest-driven)
# ---------------------------------------------------------------------------

class TestBuildForbiddenBaseIds:
    def test_unions_all_three_splits(self, tmp_path: Path):
        m = _write_manifest(
            tmp_path / "manifest.json",
            cal=["c1"], dev=["d1", "d2"], test=["t1"],
        )
        assert build_forbidden_base_ids(m) == {"c1", "d1", "d2", "t1"}

    def test_empty_splits_give_empty_set(self, tmp_path: Path):
        m = _write_manifest(tmp_path / "manifest.json")
        assert build_forbidden_base_ids(m) == set()

    def test_missing_manifest_exits(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            build_forbidden_base_ids(tmp_path / "nope.json")

    def test_dedupes_across_splits(self, tmp_path: Path):
        m = _write_manifest(
            tmp_path / "manifest.json",
            cal=["x"], dev=["x"], test=["x"],
        )
        assert build_forbidden_base_ids(m) == {"x"}


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
        p2 = _write_actor_csv(tmp_path / "test.csv", rows)
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
        rows = _make_actor_rows(200)
        for r in rows:
            r["tutor_response"] = "secret"
            r["human_coherence"] = "Yes"
        train, _ = create_actor_splits(rows, set(), FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)
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
    def test_full_test_size(self):
        assert FULL_TEST_SIZE == 60

    def test_full_train_cap(self):
        assert FULL_TRAIN_CAP == 55

    def test_seed(self):
        assert SEED == 42

    def test_no_mini_constants(self):
        # Mini splits were removed.
        assert not hasattr(_mod, "MINI_TRAIN_SIZE")
        assert not hasattr(_mod, "sample_mini")


# ---------------------------------------------------------------------------
# TestEndToEnd
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_pipeline_produces_two_files_no_leakage(self, tmp_path: Path):
        pool_rows = _make_actor_rows(200, "conv")
        manifest = _write_manifest(
            tmp_path / "judge_split_manifest.json",
            cal=["conv0000"], dev=["conv0001", "conv0002"], test=["conv0003"],
        )
        forbidden = build_forbidden_base_ids(manifest)
        train, test = create_actor_splits(pool_rows, forbidden, FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED)

        out = {}
        for name, rows in [("actor_train", train), ("actor_test", test)]:
            path = tmp_path / f"{name}.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=ACTOR_FIELDNAMES, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            out[name] = list(csv.DictReader(path.open()))

        assert len(out["actor_test"]) == FULL_TEST_SIZE
        assert len(out["actor_train"]) == FULL_TRAIN_CAP
        train_ids = {r["id"] for r in out["actor_train"]}
        test_ids = {r["id"] for r in out["actor_test"]}
        assert train_ids.isdisjoint(test_ids)
        assert not any(r["id"] in forbidden for r in out["actor_train"] + out["actor_test"])
        assert set(out["actor_train"][0].keys()) == set(ACTOR_FIELDNAMES)
