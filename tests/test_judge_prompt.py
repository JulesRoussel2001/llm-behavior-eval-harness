"""Tests for the versioned judge prompt: assembly helper + drift check.

These run from the repository root (pytest's cwd), so the default relative paths in
judge_prompt (judge_prompts/, data/processed_mrbench/calibration.csv) resolve.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from claude_behavior_eval import judge
from claude_behavior_eval.judge_prompt import (
    CALIBRATION_MARKER,
    assemble_prompt,
    build_calibration_examples,
    prompt_sha256,
    read_frozen,
    version_path,
)

_REPO_ROOT = Path(__file__).parent.parent
_V0_SHA = "584dabbf45e0e748749a77b7be68f2fe0991f77b62b21206d4e772557c7ecb26"


# --------------------------------------------------------------------------- #
# assemble_prompt / helper
# --------------------------------------------------------------------------- #

class TestAssemble:
    def test_frozen_version_is_byte_identical_to_judge_system_prompt(self):
        # The FROZEN version must assemble byte-for-byte to judge.py's _SYSTEM_PROMPT.
        assert assemble_prompt(read_frozen()) == judge._SYSTEM_PROMPT

    def test_v0_sha_is_stable(self):
        assert prompt_sha256(assemble_prompt("v0")) == _V0_SHA

    def test_examples_block_appears_once_in_prompt(self):
        examples = build_calibration_examples()
        assert judge._SYSTEM_PROMPT.count(examples) == 1

    def test_missing_version_raises_filenotfound(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            assemble_prompt("does_not_exist", prompts_dir=tmp_path)

    def test_missing_marker_raises_valueerror(self, tmp_path: Path):
        (tmp_path / "vx.txt").write_text("no marker here", encoding="utf-8")
        with pytest.raises(ValueError, match="missing"):
            assemble_prompt("vx", prompts_dir=tmp_path)

    def test_duplicate_marker_raises_valueerror(self, tmp_path: Path):
        (tmp_path / "vx.txt").write_text(
            f"{CALIBRATION_MARKER} ... {CALIBRATION_MARKER}", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="occurs 2 times"):
            assemble_prompt("vx", prompts_dir=tmp_path)


class TestReadFrozen:
    def test_reads_and_strips(self, tmp_path: Path):
        (tmp_path / "FROZEN").write_text("v0\n", encoding="utf-8")
        assert read_frozen(tmp_path) == "v0"

    def test_missing_frozen_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_frozen(tmp_path)

    def test_repo_frozen_names_existing_version(self):
        # FROZEN must name a version whose template file exists (not a hard-coded name).
        assert version_path(read_frozen()).exists()


# --------------------------------------------------------------------------- #
# 05_check_prompt_drift.py — reads FROZEN, PASS/FAIL with version + sha
# --------------------------------------------------------------------------- #

def _load_drift_module():
    path = _REPO_ROOT / "scripts" / "05_check_prompt_drift.py"
    spec = importlib.util.spec_from_file_location("check_prompt_drift", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class TestDriftCheck:
    def test_pass_reports_frozen_version_and_sha(self, capsys):
        version = read_frozen()
        sha = prompt_sha256(assemble_prompt(version))
        mod = _load_drift_module()
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "PASS" in out
        assert f"version {version}" in out
        assert sha in out

    def test_fail_when_frozen_missing(self, tmp_path: Path, capsys):
        mod = _load_drift_module()
        old = os.getcwd()
        try:
            os.chdir(tmp_path)  # no judge_prompts/ here → read_frozen fails
            with pytest.raises(SystemExit) as exc:
                mod.main()
        finally:
            os.chdir(old)
        assert exc.value.code == 1
        assert "FAIL" in capsys.readouterr().out
