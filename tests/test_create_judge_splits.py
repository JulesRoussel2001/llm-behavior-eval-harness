"""Tests for scripts/01_create_splits.py judge split creation logic."""
from __future__ import annotations

import csv
import importlib.util
import random
from pathlib import Path

import pytest

# Import the script module without executing main()
_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "01_create_splits.py"
_spec = importlib.util.spec_from_file_location("create_splits", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_base_id = _mod._base_id
_is_clean = _mod._is_clean
_to_bools = _mod._to_bools
_coverage_ok = _mod._coverage_ok
_coverage_score = _mod._coverage_score
CALIBRATION_SIZE = _mod.CALIBRATION_SIZE
DEV_SIZE = _mod.DEV_SIZE
TEST_SIZE = _mod.TEST_SIZE
TOTAL_NEEDED = _mod.TOTAL_NEEDED
SEED = _mod.SEED
DIM_NAMES = _mod.DIM_NAMES
BOOL_COLS = _mod.BOOL_COLS
TONE_COL = _mod.TONE_COL


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

def _make_row(
    conv_idx: int,
    model: str = "GPT4",
    all_true: bool = True,
    tone: str = "Encouraging",
) -> dict:
    """Create a minimal clean judge row."""
    val = "Yes" if all_true else "No"
    row = {
        "id": f"conv{conv_idx:04d}_{model}",
        "human_mistake_identification": val,
        "human_mistake_location": val,
        "human_answer_revealing_appropriate": val,
        "human_providing_guidance": val,
        "human_actionability": val,
        "human_coherence": val,
        "human_human_likeness": val,
        "human_tutor_tone": tone,
    }
    return row


def _make_pool(
    n_conversations: int,
    models: list[str] | None = None,
) -> list[dict]:
    """
    Create a pool of clean judge rows with balanced True/False labels.

    Even-indexed conversations have all_true=True + Encouraging tone.
    Odd-indexed conversations have all_true=False + Neutral tone.
    Each conversation gets one row per model.
    """
    if models is None:
        models = ["GPT4", "Gemini"]
    rows = []
    for i in range(n_conversations):
        all_true = (i % 2 == 0)
        tone = "Encouraging" if all_true else "Neutral"
        for model in models:
            rows.append(_make_row(i, model, all_true=all_true, tone=tone))
    return rows


def _write_raw_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("id\n", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# TestBaseId
# ---------------------------------------------------------------------------

class TestBaseId:
    def test_strips_model_suffix(self):
        assert _base_id("conv0001_GPT4") == "conv0001"

    def test_strips_multipart_model_name(self):
        assert _base_id("conv0042_Phi3Mini") == "conv0042"

    def test_single_underscore(self):
        assert _base_id("abc_XYZ") == "abc"

    def test_multiple_underscores_strips_last(self):
        # conv IDs themselves never have underscores; only the model suffix does
        assert _base_id("someconv_ModelName") == "someconv"

    def test_consistent_with_actor_split_helper(self):
        # Verify stripping is rsplit-based (last segment only)
        full_id = "longconvid_GPT4Turbo"
        base = _base_id(full_id)
        assert "_" not in base or base.count("_") < full_id.count("_")


# ---------------------------------------------------------------------------
# TestIsClean
# ---------------------------------------------------------------------------

class TestIsClean:
    def _clean(self) -> dict:
        return _make_row(0)

    def test_clean_row_passes(self):
        ok, reason = _is_clean(self._clean())
        assert ok
        assert reason == ""

    def test_offensive_tone_excluded(self):
        row = self._clean()
        row["human_tutor_tone"] = "Offensive"
        ok, reason = _is_clean(row)
        assert not ok
        assert reason == "offensive_tone"

    def test_empty_bool_col_excluded(self):
        row = self._clean()
        row["human_mistake_identification"] = ""
        ok, reason = _is_clean(row)
        assert not ok
        assert reason == "missing_bool"

    def test_invalid_tone_excluded(self):
        row = self._clean()
        row["human_tutor_tone"] = "SomethingElse"
        ok, reason = _is_clean(row)
        assert not ok
        assert reason == "invalid_tone"

    def test_empty_tone_is_missing_tone(self):
        row = self._clean()
        row["human_tutor_tone"] = ""
        ok, reason = _is_clean(row)
        assert not ok
        assert reason == "missing_tone"

    def test_neutral_tone_passes(self):
        row = self._clean()
        row["human_tutor_tone"] = "Neutral"
        ok, _ = _is_clean(row)
        assert ok

    def test_encouraging_tone_passes(self):
        row = self._clean()
        row["human_tutor_tone"] = "Encouraging"
        ok, _ = _is_clean(row)
        assert ok

    def test_bool_col_accepts_no(self):
        row = _make_row(0, all_true=False)
        ok, _ = _is_clean(row)
        assert ok

    def test_bool_col_accepts_true_false(self):
        row = self._clean()
        row["human_mistake_identification"] = "True"
        row["human_mistake_location"] = "False"
        ok, _ = _is_clean(row)
        assert ok

    def test_bool_col_accepts_1_0(self):
        row = self._clean()
        row["human_mistake_identification"] = "1"
        row["human_mistake_location"] = "0"
        ok, _ = _is_clean(row)
        assert ok

    def test_bool_col_case_insensitive(self):
        row = self._clean()
        row["human_mistake_identification"] = "YES"
        ok, _ = _is_clean(row)
        assert ok


# ---------------------------------------------------------------------------
# TestToBools
# ---------------------------------------------------------------------------

class TestToBools:
    def test_all_yes_encouraging_produces_all_true(self):
        row = _make_row(0, all_true=True, tone="Encouraging")
        bools = _to_bools(row)
        assert len(bools) == len(DIM_NAMES)
        assert all(bools)

    def test_all_no_neutral_produces_all_false(self):
        row = _make_row(0, all_true=False, tone="Neutral")
        bools = _to_bools(row)
        assert len(bools) == len(DIM_NAMES)
        assert not any(bools)

    def test_encouraging_maps_to_true(self):
        row = _make_row(0, all_true=True, tone="Encouraging")
        bools = _to_bools(row)
        assert bools[-1] is True  # tutor_tone is last

    def test_neutral_maps_to_false(self):
        row = _make_row(0, all_true=True, tone="Neutral")
        bools = _to_bools(row)
        assert bools[-1] is False

    def test_length_equals_dim_names(self):
        row = _make_row(0)
        assert len(_to_bools(row)) == len(DIM_NAMES)

    def test_bool_col_yes_maps_true(self):
        row = _make_row(0, all_true=True)
        bools = _to_bools(row)
        # First 7 bools correspond to BOOL_COLS
        for i in range(7):
            assert bools[i] is True

    def test_bool_col_no_maps_false(self):
        row = _make_row(0, all_true=False, tone="Neutral")
        bools = _to_bools(row)
        for i in range(7):
            assert bools[i] is False


# ---------------------------------------------------------------------------
# TestCoverageOk
# ---------------------------------------------------------------------------

class TestCoverageOk:
    def _bool_rows(self, n_true: int, n_false: int) -> list[list[bool]]:
        """Make rows with the same value for all dimensions."""
        return [[True] * len(DIM_NAMES)] * n_true + [[False] * len(DIM_NAMES)] * n_false

    def test_strong_satisfied(self):
        rows = self._bool_rows(5, 5)
        assert _coverage_ok(rows, 5, 5)

    def test_strong_fails_insufficient_true(self):
        rows = self._bool_rows(4, 6)
        assert not _coverage_ok(rows, 5, 5)

    def test_strong_fails_insufficient_false(self):
        rows = self._bool_rows(6, 4)
        assert not _coverage_ok(rows, 5, 5)

    def test_fallback_satisfied(self):
        rows = self._bool_rows(2, 2)
        assert _coverage_ok(rows, 2, 2)

    def test_fallback_fails_with_single_class(self):
        rows = self._bool_rows(4, 0)
        assert not _coverage_ok(rows, 2, 2)

    def test_empty_rows_fails(self):
        assert not _coverage_ok([], 1, 1)

    def test_mixed_dimensions(self):
        # One dimension has 0 False values → fails
        rows = [[True] * len(DIM_NAMES) for _ in range(5)]
        rows += [[False] + [True] * (len(DIM_NAMES) - 1) for _ in range(5)]
        # dim 0: 5T 5F → ok. All other dims: 10T 0F → fails
        assert not _coverage_ok(rows, 5, 5)


# ---------------------------------------------------------------------------
# TestCoverageScore
# ---------------------------------------------------------------------------

class TestCoverageScore:
    def test_perfect_score(self):
        rows = [[True] * len(DIM_NAMES)] * 5 + [[False] * len(DIM_NAMES)] * 5
        score = _coverage_score(rows, 5, 5)
        assert score == len(DIM_NAMES) * 2

    def test_zero_score_when_no_min_met(self):
        # Only 1 True, 0 False: can't satisfy min_true=2 or min_false=1 for any dim
        rows = [[True] * len(DIM_NAMES)]
        score = _coverage_score(rows, 2, 1)
        assert score == 0

    def test_score_bounded(self):
        rows = [[True] * len(DIM_NAMES)] * 5 + [[False] * len(DIM_NAMES)] * 5
        score = _coverage_score(rows, 5, 5)
        assert 0 <= score <= len(DIM_NAMES) * 2


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_calibration_size(self):
        assert CALIBRATION_SIZE == 3

    def test_dev_size(self):
        assert DEV_SIZE == 20

    def test_test_size(self):
        assert TEST_SIZE == 10

    def test_total_needed(self):
        assert TOTAL_NEEDED == CALIBRATION_SIZE + DEV_SIZE + TEST_SIZE

    def test_total_needed_value(self):
        assert TOTAL_NEEDED == 33

    def test_seed(self):
        assert SEED == 42

    def test_dim_names_length(self):
        assert len(DIM_NAMES) == 8

    def test_bool_cols_length(self):
        assert len(BOOL_COLS) == 7

    def test_tone_col(self):
        assert TONE_COL == "human_tutor_tone"


# ---------------------------------------------------------------------------
# TestBaseIdDisjoint (core constraint)
# ---------------------------------------------------------------------------

class TestBaseIdDisjoint:
    """Verify the base-conversation-ID disjoint constraint through end-to-end simulation."""

    def _run_main(self, tmp_path: Path, pool: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
        """Write synthetic raw CSV, run main(), read back outputs."""
        data_dir = tmp_path / "data" / "processed_mrbench"
        data_dir.mkdir(parents=True)
        _write_raw_csv(data_dir / "judge_validation_raw.csv", pool)

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            _mod.main()
        finally:
            os.chdir(old_cwd)

        def _read(name):
            with (data_dir / name).open(encoding="utf-8") as f:
                return list(csv.DictReader(f))

        return _read("calibration.csv"), _read("judge_dev.csv"), _read("judge_test.csv")

    def test_calibration_dev_base_ids_disjoint(self, tmp_path: Path):
        pool = _make_pool(80)
        cal, dev, _ = self._run_main(tmp_path, pool)
        cal_bases = {_base_id(r["id"]) for r in cal}
        dev_bases = {_base_id(r["id"]) for r in dev}
        assert cal_bases.isdisjoint(dev_bases)

    def test_calibration_test_base_ids_disjoint(self, tmp_path: Path):
        pool = _make_pool(80)
        cal, _, test = self._run_main(tmp_path, pool)
        cal_bases = {_base_id(r["id"]) for r in cal}
        test_bases = {_base_id(r["id"]) for r in test}
        assert cal_bases.isdisjoint(test_bases)

    def test_dev_test_base_ids_disjoint(self, tmp_path: Path):
        pool = _make_pool(80)
        _, dev, test = self._run_main(tmp_path, pool)
        dev_bases = {_base_id(r["id"]) for r in dev}
        test_bases = {_base_id(r["id"]) for r in test}
        assert dev_bases.isdisjoint(test_bases)

    def test_no_duplicate_base_ids_in_calibration(self, tmp_path: Path):
        pool = _make_pool(80)
        cal, _, _ = self._run_main(tmp_path, pool)
        bases = [_base_id(r["id"]) for r in cal]
        assert len(bases) == len(set(bases))

    def test_no_duplicate_base_ids_in_dev(self, tmp_path: Path):
        pool = _make_pool(80)
        _, dev, _ = self._run_main(tmp_path, pool)
        bases = [_base_id(r["id"]) for r in dev]
        assert len(bases) == len(set(bases))

    def test_no_duplicate_base_ids_in_test(self, tmp_path: Path):
        pool = _make_pool(80)
        _, _, test = self._run_main(tmp_path, pool)
        bases = [_base_id(r["id"]) for r in test]
        assert len(bases) == len(set(bases))

    def test_calibration_correct_size(self, tmp_path: Path):
        pool = _make_pool(80)
        cal, _, _ = self._run_main(tmp_path, pool)
        assert len(cal) == CALIBRATION_SIZE

    def test_dev_correct_size(self, tmp_path: Path):
        pool = _make_pool(80)
        _, dev, _ = self._run_main(tmp_path, pool)
        assert len(dev) == DEV_SIZE

    def test_test_correct_size(self, tmp_path: Path):
        pool = _make_pool(80)
        _, _, test = self._run_main(tmp_path, pool)
        assert len(test) == TEST_SIZE

    def test_deterministic_with_same_seed(self, tmp_path: Path):
        """Running main() twice on the same input produces identical output."""
        pool = _make_pool(80)
        data_dir = tmp_path / "data" / "processed_mrbench"
        data_dir.mkdir(parents=True)
        _write_raw_csv(data_dir / "judge_validation_raw.csv", pool)

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            _mod.main()
            cal1 = list(csv.DictReader((data_dir / "calibration.csv").open(encoding="utf-8")))
            dev1 = list(csv.DictReader((data_dir / "judge_dev.csv").open(encoding="utf-8")))
            test1 = list(csv.DictReader((data_dir / "judge_test.csv").open(encoding="utf-8")))
            _mod.main()
            cal2 = list(csv.DictReader((data_dir / "calibration.csv").open(encoding="utf-8")))
            dev2 = list(csv.DictReader((data_dir / "judge_dev.csv").open(encoding="utf-8")))
            test2 = list(csv.DictReader((data_dir / "judge_test.csv").open(encoding="utf-8")))
        finally:
            os.chdir(old_cwd)

        assert [r["id"] for r in cal1] == [r["id"] for r in cal2]
        assert [r["id"] for r in dev1] == [r["id"] for r in dev2]
        assert [r["id"] for r in test1] == [r["id"] for r in test2]

    def test_all_output_rows_are_clean(self, tmp_path: Path):
        pool = _make_pool(80)
        cal, dev, test = self._run_main(tmp_path, pool)
        for row in cal + dev + test:
            ok, reason = _is_clean(row)
            assert ok, f"Unclean row in output: {reason} — {row['id']}"

    def test_tutor_tone_encouraging_neutral_only(self, tmp_path: Path):
        pool = _make_pool(80)
        cal, dev, test = self._run_main(tmp_path, pool)
        for row in cal + dev + test:
            assert row[TONE_COL] in {"Encouraging", "Neutral"}, (
                f"Unexpected tone {row[TONE_COL]!r} in {row['id']}"
            )

    def test_offensive_rows_excluded(self, tmp_path: Path):
        pool = _make_pool(60)
        # Add offensive rows — these must be excluded
        for i in range(60, 70):
            row = _make_row(i, tone="Offensive")
            pool.append(row)
        cal, dev, test = self._run_main(tmp_path, pool)
        for row in cal + dev + test:
            assert row[TONE_COL] != "Offensive"

    def test_exits_when_not_enough_distinct_base_ids(self, tmp_path: Path):
        # Only 20 distinct base conversations — need 33
        pool = _make_pool(20)
        data_dir = tmp_path / "data" / "processed_mrbench"
        data_dir.mkdir(parents=True)
        _write_raw_csv(data_dir / "judge_validation_raw.csv", pool)

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit):
                _mod.main()
        finally:
            os.chdir(old_cwd)

    def test_multi_model_pool_only_one_row_per_base_in_each_split(self, tmp_path: Path):
        """With multiple models per conversation, each split gets at most one row per conv."""
        # 60 conversations × 4 models each = 240 rows, plenty of base IDs
        pool = _make_pool(60, models=["GPT4", "Gemini", "Claude", "Phi3"])
        cal, dev, test = self._run_main(tmp_path, pool)
        for split, label in [(cal, "calibration"), (dev, "judge_dev"), (test, "judge_test")]:
            bases = [_base_id(r["id"]) for r in split]
            assert len(bases) == len(set(bases)), f"Duplicate base IDs in {label}"


# ---------------------------------------------------------------------------
# TestToneBoolConversion
# ---------------------------------------------------------------------------

class TestToneBoolConversion:
    """Verify Encouraging/Neutral correctly maps to True/False in coverage checks."""

    def test_encouraging_counts_as_true_in_coverage(self):
        rows = [_make_row(i, tone="Encouraging") for i in range(5)]
        rows += [_make_row(i + 5, tone="Neutral", all_true=False) for i in range(5)]
        bools = [_to_bools(r) for r in rows]
        # Last dim is tutor_tone: 5 True, 5 False
        tone_idx = len(DIM_NAMES) - 1
        tone_trues = sum(b[tone_idx] for b in bools)
        tone_falses = len(bools) - tone_trues
        assert tone_trues == 5
        assert tone_falses == 5

    def test_neutral_counts_as_false_in_coverage(self):
        rows = [_make_row(i, tone="Neutral", all_true=False) for i in range(10)]
        bools = [_to_bools(r) for r in rows]
        tone_idx = len(DIM_NAMES) - 1
        assert sum(b[tone_idx] for b in bools) == 0
