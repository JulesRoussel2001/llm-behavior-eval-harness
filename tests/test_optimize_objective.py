"""Tests for optimizer objective filtering: calculate_metrics(objective_dims=...)
and load_objective_dims."""
from __future__ import annotations

import json
from pathlib import Path

from claude_behavior_eval.optimize import calculate_metrics, load_objective_dims
from claude_behavior_eval.schemas import MRBenchEvaluation

DIMS = list(MRBenchEvaluation.model_fields.keys())


def _scores(**overrides: bool) -> dict:
    return {d: {"reason": "r", "passed": overrides.get(d, True)} for d in DIMS}


def _write_jsonl(tmp_path: Path) -> Path:
    rows = [
        {"item_id": "a", "deterministic_passed": True, "judge_scores": _scores()},
        {"item_id": "b", "deterministic_passed": True,
         "judge_scores": _scores(actionability=False)},
    ]
    path = tmp_path / "iter.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_full_metrics_include_all_dimensions(tmp_path: Path):
    m = calculate_metrics(_write_jsonl(tmp_path))
    for d in DIMS:
        assert f"{d}_pass_rate" in m
    assert "judge_macro_pass_rate" in m
    assert "deterministic_pass_rate" in m


def test_objective_metrics_exclude_unvalidated(tmp_path: Path):
    m = calculate_metrics(_write_jsonl(tmp_path), objective_dims=["coherence", "actionability"])
    assert set(m.keys()) == {
        "deterministic_pass_rate",
        "coherence_pass_rate",
        "actionability_pass_rate",
        "judge_macro_pass_rate",
    }
    # excluded dims appear under no key
    assert "tutor_tone_pass_rate" not in m
    assert "providing_guidance_pass_rate" not in m


def test_objective_macro_is_mean_over_validated_only(tmp_path: Path):
    m = calculate_metrics(_write_jsonl(tmp_path), objective_dims=["coherence", "actionability"])
    assert m["coherence_pass_rate"] == 100.0        # both rows pass
    assert m["actionability_pass_rate"] == 50.0     # one row passes
    assert m["judge_macro_pass_rate"] == 75.0       # mean over the two only


def test_load_objective_dims(tmp_path: Path):
    spec = {"validated": ["coherence", "human_likeness"], "excluded": ["tutor_tone"],
            "source": "x.jsonl"}
    path = tmp_path / "judge_validated_dimensions.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    dims, loaded = load_objective_dims(path)
    assert dims == ["coherence", "human_likeness"]
    assert loaded["source"] == "x.jsonl"
