"""Tests for scripts/07_disagreements.py FP/FN grouping and rendering."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).parent.parent / "scripts" / "07_disagreements.py"
_spec = importlib.util.spec_from_file_location("disagreements", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

DIMS = _mod.DIMS
analyze = _mod.analyze
render_markdown = _mod.render_markdown


def _row(item_id, human, judge, reason="", excerpt="excerpt text"):
    """Build a full row; `human`/`judge` set the target dim, others agree (True)."""
    hl = {d: True for d in DIMS}
    jl = {d: True for d in DIMS}
    reasons = {d: "" for d in DIMS}
    hl["mistake_identification"] = human
    jl["mistake_identification"] = judge
    reasons["mistake_identification"] = reason
    return {
        "item_id": item_id,
        "human_labels": hl,
        "judge_labels": jl,
        "judge_reasons": reasons,
        "tutor_response_excerpt": excerpt,
    }


def test_fp_and_fn_partition():
    rows = [
        _row("fp1", human=False, judge=True, reason="tutor is encouraging here"),
        _row("fn1", human=True, judge=False, reason="tutor misses the mistake"),
        _row("agree", human=True, judge=True, reason="ok"),
    ]
    a = analyze(rows)
    mi = a["mistake_identification"]
    assert [e["item_id"] for e in mi["fp"]] == ["fp1"]
    assert [e["item_id"] for e in mi["fn"]] == ["fn1"]
    # other dims all agree → no disagreements
    assert a["coherence"]["fp"] == [] and a["coherence"]["fn"] == []


def test_excerpt_truncated_to_300():
    rows = [_row("fp1", human=False, judge=True, excerpt="X" * 500)]
    a = analyze(rows)
    assert len(a["mistake_identification"]["fp"][0]["excerpt"]) == 300


def test_word_frequency_surfaces_reason_words():
    rows = [
        _row("fp1", human=False, judge=True, reason="encouraging encouraging tone"),
        _row("fp2", human=False, judge=True, reason="encouraging language"),
    ]
    a = analyze(rows)
    words = dict(a["mistake_identification"]["fp_words"])
    assert words.get("encouraging") == 3
    # stopwords excluded
    assert "the" not in words


def test_cap_at_25_with_more_line():
    rows = [_row(f"fn{i}", human=True, judge=False, reason="miss") for i in range(30)]
    a = analyze(rows)
    assert len(a["mistake_identification"]["fn"]) == 30  # analysis keeps all
    md = render_markdown(a, "src.jsonl")
    assert "... 5 more" in md  # render caps at 25


def test_render_contains_all_dimensions():
    a = analyze([_row("fp1", human=False, judge=True)])
    md = render_markdown(a, "src.jsonl")
    for d in DIMS:
        assert f"## {d}" in md
