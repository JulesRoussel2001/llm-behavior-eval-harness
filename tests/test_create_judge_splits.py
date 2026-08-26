"""Tests for scripts/01_create_splits.py judge split creation logic.

The split logic changed to: pin calibration, sample 80 conversations (seed=42),
split into judge_dev=40 / judge_test=40 conversations, and include ALL rows of each
selected conversation (no representative-row selection, no coverage search).
"""
from __future__ import annotations

import csv
import importlib.util
import os
from pathlib import Path

import pytest

# Import the script module without executing main()
_REPO_ROOT = Path(__file__).parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "01_create_splits.py"
_spec = importlib.util.spec_from_file_location("create_splits", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_base_id = _mod._base_id
rejection_reason = _mod.rejection_reason
filter_rows = _mod.filter_rows
load_pinned_calibration = _mod.load_pinned_calibration
PINNED_CALIBRATION_IDS = _mod.PINNED_CALIBRATION_IDS
SELECTED_CONVERSATIONS = _mod.SELECTED_CONVERSATIONS
DEV_CONVERSATIONS = _mod.DEV_CONVERSATIONS
TEST_CONVERSATIONS = _mod.TEST_CONVERSATIONS
SEED = _mod.SEED

_REAL_CALIBRATION = _REPO_ROOT / "data" / "processed_mrbench" / "calibration.csv"


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
    return {
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


def _make_pool(n_conversations: int, models: list[str] | None = None) -> list[dict]:
    """Create a pool of judge rows; each conversation gets one row per model."""
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


def _run_main(
    tmp_path: Path,
    pool: list[dict],
    calibration_ids: list[str],
    monkeypatch,
) -> tuple[bytes, list[dict], list[dict], dict]:
    """Set up a synthetic repo, pin calibration to `calibration_ids`, run main().

    Returns (calibration_bytes_after, dev_rows, test_rows, manifest).
    """
    data_dir = tmp_path / "data" / "processed_mrbench"
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_raw_csv(data_dir / "judge_validation_raw.csv", pool)

    # Build a calibration.csv from the chosen ids (one row each, matching order).
    by_id = {r["id"]: r for r in pool}
    cal_rows = [by_id[i] for i in calibration_ids]
    fieldnames = list(pool[0].keys())
    with (data_dir / "calibration.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cal_rows)

    monkeypatch.setattr(_mod, "PINNED_CALIBRATION_IDS", list(calibration_ids))

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        _mod.main()
    finally:
        os.chdir(old_cwd)

    cal_bytes = (data_dir / "calibration.csv").read_bytes()
    dev = list(csv.DictReader((data_dir / "judge_dev.csv").open(encoding="utf-8")))
    test = list(csv.DictReader((data_dir / "judge_test.csv").open(encoding="utf-8")))
    import json
    manifest = json.loads((data_dir / "judge_split_manifest.json").read_text())
    return cal_bytes, dev, test, manifest


# ---------------------------------------------------------------------------
# TestBaseId
# ---------------------------------------------------------------------------

class TestBaseId:
    def test_strips_model_suffix(self):
        assert _base_id("conv0001_GPT4") == "conv0001"

    def test_strips_multipart_model_name(self):
        assert _base_id("conv0042_Phi3Mini") == "conv0042"

    def test_hyphenated_conv_id_keeps_hyphens(self):
        assert _base_id("5780-2d7f22e8-1486_Mistral") == "5780-2d7f22e8-1486"


# ---------------------------------------------------------------------------
# TestRowFilter (the metric-parser-based filter shared with validate_judge)
# ---------------------------------------------------------------------------

class TestRowFilter:
    def test_clean_row_accepted(self):
        assert rejection_reason(_make_row(0, all_true=True, tone="Encouraging")) is None
        assert rejection_reason(_make_row(0, all_true=False, tone="Neutral")) is None

    def test_offensive_tone_rejected(self):
        row = _make_row(0, tone="Offensive")
        assert rejection_reason(row) == "offensive_tone"

    def test_empty_label_rejected(self):
        row = _make_row(0)
        row["human_mistake_identification"] = ""
        assert rejection_reason(row) == "missing_label"

    def test_unknown_label_rejected(self):
        row = _make_row(0)
        row["human_mistake_identification"] = "maybe"
        assert rejection_reason(row) == "invalid_label"

    def test_filter_rows_partitions_and_counts(self):
        rows = [
            _make_row(0, tone="Encouraging"),            # kept
            _make_row(1, tone="Offensive"),              # offensive_tone
            _make_row(2),                                # kept
        ]
        bad_empty = _make_row(3)
        bad_empty["human_coherence"] = ""
        rows.append(bad_empty)                           # missing_label
        kept, reasons = filter_rows(rows)
        assert len(kept) == 2
        assert reasons["offensive_tone"] == 1
        assert reasons["missing_label"] == 1
        assert reasons["invalid_label"] == 0


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_selected_conversations(self):
        assert SELECTED_CONVERSATIONS == 80

    def test_dev_conversations(self):
        assert DEV_CONVERSATIONS == 40

    def test_test_conversations(self):
        assert TEST_CONVERSATIONS == 40

    def test_dev_plus_test_equals_selected(self):
        assert DEV_CONVERSATIONS + TEST_CONVERSATIONS == SELECTED_CONVERSATIONS

    def test_seed(self):
        assert SEED == 42


# ---------------------------------------------------------------------------
# TestPinnedCalibration (the frozen calibration guarantee)
# ---------------------------------------------------------------------------

class TestPinnedCalibration:
    def test_pinned_ids_are_exactly_three(self):
        assert len(PINNED_CALIBRATION_IDS) == 3

    @pytest.mark.skipif(not _REAL_CALIBRATION.exists(), reason="real calibration.csv absent")
    def test_real_calibration_ids_match_pinned_three(self):
        ids = [r["id"] for r in csv.DictReader(_REAL_CALIBRATION.open(encoding="utf-8"))]
        assert ids == PINNED_CALIBRATION_IDS

    def test_load_pinned_calibration_accepts_matching_file(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "calibration.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id"])
            w.writeheader()
            for i in ["a_X", "b_Y", "c_Z"]:
                w.writerow({"id": i})
        monkeypatch.setattr(_mod, "PINNED_CALIBRATION_IDS", ["a_X", "b_Y", "c_Z"])
        assert load_pinned_calibration(p) == ["a_X", "b_Y", "c_Z"]

    def test_load_pinned_calibration_rejects_mismatch(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "calibration.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id"])
            w.writeheader()
            w.writerow({"id": "WRONG_X"})
        monkeypatch.setattr(_mod, "PINNED_CALIBRATION_IDS", ["a_X", "b_Y", "c_Z"])
        with pytest.raises(SystemExit):
            load_pinned_calibration(p)

    def test_load_pinned_calibration_missing_file_exits(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            load_pinned_calibration(tmp_path / "nope.csv")

    def test_calibration_written_back_byte_identical(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "calibration.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "x"])
            w.writeheader()
            for i in ["a_X", "b_Y", "c_Z"]:
                w.writerow({"id": i, "x": "v"})
        before = p.read_bytes()
        monkeypatch.setattr(_mod, "PINNED_CALIBRATION_IDS", ["a_X", "b_Y", "c_Z"])
        load_pinned_calibration(p)
        assert p.read_bytes() == before


# ---------------------------------------------------------------------------
# TestEndToEnd (leakage/disjointness + all-rows + manifest)
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """100 conversations × 2 models. Pin 3 for calibration; expect 40/40 splits."""

    CAL_IDS = ["conv0000_GPT4", "conv0001_GPT4", "conv0002_GPT4"]

    def _run(self, tmp_path, monkeypatch, n_conv=100, models=None):
        pool = _make_pool(n_conv, models=models)
        return pool, _run_main(tmp_path, pool, self.CAL_IDS, monkeypatch)

    def test_dev_has_40_conversations(self, tmp_path, monkeypatch):
        _, (_, dev, _, _) = self._run(tmp_path, monkeypatch)
        assert len({_base_id(r["id"]) for r in dev}) == DEV_CONVERSATIONS

    def test_test_has_40_conversations(self, tmp_path, monkeypatch):
        _, (_, _, test, _) = self._run(tmp_path, monkeypatch)
        assert len({_base_id(r["id"]) for r in test}) == TEST_CONVERSATIONS

    def test_all_rows_of_selected_conversations_included(self, tmp_path, monkeypatch):
        pool, (_, dev, test, _) = self._run(tmp_path, monkeypatch)
        counts = {}
        for r in pool:
            counts.setdefault(_base_id(r["id"]), 0)
            counts[_base_id(r["id"])] += 1
        for split in (dev, test):
            got = {}
            for r in split:
                got.setdefault(_base_id(r["id"]), 0)
                got[_base_id(r["id"])] += 1
            for base, c in got.items():
                assert c == counts[base], f"conversation {base} not fully included"

    def test_calibration_dev_test_conversations_disjoint(self, tmp_path, monkeypatch):
        _, (_, dev, test, _) = self._run(tmp_path, monkeypatch)
        cal_bases = {_base_id(i) for i in self.CAL_IDS}
        dev_bases = {_base_id(r["id"]) for r in dev}
        test_bases = {_base_id(r["id"]) for r in test}
        assert cal_bases.isdisjoint(dev_bases)
        assert cal_bases.isdisjoint(test_bases)
        assert dev_bases.isdisjoint(test_bases)

    def test_manifest_matches_outputs(self, tmp_path, monkeypatch):
        # Synthetic pool is all-clean → rows_after_filtering == written rows.
        _, (_, dev, test, manifest) = self._run(tmp_path, monkeypatch)
        assert manifest["judge_dev"]["num_conversations"] == DEV_CONVERSATIONS
        assert manifest["judge_test"]["num_conversations"] == TEST_CONVERSATIONS
        assert manifest["judge_dev"]["rows_after_filtering"] == len(dev)
        assert manifest["judge_test"]["rows_after_filtering"] == len(test)
        assert manifest["judge_dev"]["excluded_rows"] == 0
        assert manifest["calibration"]["num_conversations"] == 3
        assert set(manifest["judge_dev"]["conversation_ids"]) == {_base_id(r["id"]) for r in dev}

    def test_manifest_conversation_ids_disjoint(self, tmp_path, monkeypatch):
        _, (_, _, _, manifest) = self._run(tmp_path, monkeypatch)
        cal = set(manifest["calibration"]["conversation_ids"])
        dev = set(manifest["judge_dev"]["conversation_ids"])
        test = set(manifest["judge_test"]["conversation_ids"])
        assert cal.isdisjoint(dev) and cal.isdisjoint(test) and dev.isdisjoint(test)

    def test_calibration_conversations_never_in_splits(self, tmp_path, monkeypatch):
        _, (_, dev, test, _) = self._run(tmp_path, monkeypatch)
        cal_bases = {_base_id(i) for i in self.CAL_IDS}
        for r in dev + test:
            assert _base_id(r["id"]) not in cal_bases

    def test_calibration_bytes_unchanged_by_main(self, tmp_path, monkeypatch):
        # Capture calibration bytes before main, compare with after.
        pool = _make_pool(100)
        data_dir = tmp_path / "data" / "processed_mrbench"
        # _run_main writes calibration.csv then runs main(); we re-run and compare.
        cal_bytes_after, _, _, _ = _run_main(tmp_path, pool, self.CAL_IDS, monkeypatch)
        # Rebuild the same calibration.csv independently and compare bytes.
        by_id = {r["id"]: r for r in pool}
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(pool[0].keys()))
        w.writeheader()
        for i in self.CAL_IDS:
            w.writerow(by_id[i])
        assert cal_bytes_after == buf.getvalue().encode("utf-8")

    def test_deterministic_same_seed(self, tmp_path, monkeypatch):
        pool = _make_pool(100)
        _, dev1, test1, _ = _run_main(tmp_path, pool, self.CAL_IDS, monkeypatch)
        _, dev2, test2, _ = _run_main(tmp_path, pool, self.CAL_IDS, monkeypatch)
        assert [r["id"] for r in dev1] == [r["id"] for r in dev2]
        assert [r["id"] for r in test1] == [r["id"] for r in test2]

    def test_exits_when_not_enough_conversations(self, tmp_path, monkeypatch):
        # 80 conversations - 3 calibration = 77 < 80 needed → SystemExit
        pool = _make_pool(80)
        with pytest.raises(SystemExit):
            _run_main(tmp_path, pool, self.CAL_IDS, monkeypatch)

    def test_multi_model_conversations_all_rows_kept(self, tmp_path, monkeypatch):
        # 4 models per conversation; each selected conv contributes 4 CLEAN rows.
        pool, (_, dev, test, _) = self._run(
            tmp_path, monkeypatch, n_conv=100, models=["GPT4", "Gemini", "Claude", "Phi3"]
        )
        for split in (dev, test):
            per = {}
            for r in split:
                per.setdefault(_base_id(r["id"]), 0)
                per[_base_id(r["id"])] += 1
            assert all(c == 4 for c in per.values())


class TestEndToEndFiltering:
    """Every conversation carries 2 clean rows + 1 Offensive row that must be dropped."""

    CAL_IDS = ["conv0000_Clean0", "conv0001_Clean0", "conv0002_Clean0"]

    def _pool(self, n_conv=100):
        rows = []
        for i in range(n_conv):
            all_true = (i % 2 == 0)
            tone = "Encouraging" if all_true else "Neutral"
            rows.append(_make_row(i, "Clean0", all_true=all_true, tone=tone))
            rows.append(_make_row(i, "Clean1", all_true=all_true, tone=tone))
            rows.append(_make_row(i, "Offense", all_true=all_true, tone="Offensive"))
        return rows

    def test_offensive_rows_dropped_and_counted(self, tmp_path, monkeypatch):
        pool = self._pool()
        _, dev, test, manifest = _run_main(tmp_path, pool, self.CAL_IDS, monkeypatch)

        # No Offensive rows survive into either split.
        for r in dev + test:
            assert "_Offense" not in r["id"]

        for key, rows in [("judge_dev", dev), ("judge_test", test)]:
            m = manifest[key]
            assert m["num_conversations"] == 40
            assert m["rows_before_filtering"] == 40 * 3   # 3 rows per conversation
            assert m["rows_after_filtering"] == 40 * 2    # 2 clean rows survive
            assert m["rows_after_filtering"] == len(rows)
            assert m["excluded_rows"] == 40
            assert m["excluded_by_reason"]["offensive_tone"] == 40
            assert m["excluded_by_reason"]["missing_label"] == 0
            assert m["excluded_by_reason"]["invalid_label"] == 0
