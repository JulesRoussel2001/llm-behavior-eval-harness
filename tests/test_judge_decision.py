"""Tests for scripts/08_judge_decision.py: kappa/precision + the pre-registered rule."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parent.parent / "scripts" / "08_judge_decision.py"
_spec = importlib.util.spec_from_file_location("judge_decision", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

DIMS = _mod.DIMS
cohen_kappa = _mod.cohen_kappa
pass_precision = _mod.pass_precision
evaluate_dimension = _mod.evaluate_dimension
decide = _mod.decide

# Reusable (h, j) column patterns of length 10.
PASS = [(True, True)] * 5 + [(False, False)] * 3 + [(True, False)] + [(False, True)]
KAPPA_FAIL = [(True, True)] * 8 + [(False, True)] + [(True, False)]          # prec ok, kappa<0
PREC_FAIL = [(True, True)] + [(False, True)] * 4 + [(False, False)] * 5      # prec 0.2
UNDEF_PREC = [(True, False)] * 5 + [(False, False)] * 5                       # judge never True


def _rows(pairs_by_dim: dict[str, list[tuple[bool, bool]]]) -> list[dict]:
    n = len(next(iter(pairs_by_dim.values())))
    rows = []
    for i in range(n):
        hl, jl = {}, {}
        for d in DIMS:
            h, j = pairs_by_dim[d][i]
            hl[d], jl[d] = h, j
        rows.append({"item_id": f"c{i}_M", "human_labels": hl, "judge_labels": jl})
    return rows


# --------------------------------------------------------------------------- #
# pure functions
# --------------------------------------------------------------------------- #

def test_pass_precision_undefined_when_no_positive_predictions():
    assert pass_precision(0, 0) is None

def test_pass_precision_value():
    assert pass_precision(5, 1) == 5 / 6

def test_kappa_undefined_when_expected_agreement_one():
    # all agree True → pe == 1 → undefined
    assert cohen_kappa(tp=10, fp=0, fn=0, tn=0) is None

def test_kappa_defined_value_sign():
    assert cohen_kappa(tp=5, fp=1, fn=1, tn=3) > 0


# --------------------------------------------------------------------------- #
# evaluate_dimension
# --------------------------------------------------------------------------- #

def test_pass_pattern_validates():
    rows = _rows({d: PASS for d in DIMS})
    r = evaluate_dimension(rows, DIMS[0], 0.40, 0.80)
    assert r["validated"] is True and r["reasons"] == []

def test_precision_undefined_fails_and_reported():
    rows = _rows({d: UNDEF_PREC for d in DIMS})
    r = evaluate_dimension(rows, DIMS[0], 0.40, 0.80)
    assert r["validated"] is False
    assert r["precision_defined"] is False
    assert "precision_undefined" in r["reasons"]

def test_kappa_undefined_fails_and_reported():
    rows = _rows({d: [(True, True)] * 10 for d in DIMS})
    r = evaluate_dimension(rows, DIMS[0], 0.40, 0.80)
    assert r["validated"] is False
    assert r["kappa_defined"] is False
    assert "kappa_undefined" in r["reasons"]

def test_kappa_below_threshold_with_ok_precision():
    rows = _rows({d: KAPPA_FAIL for d in DIMS})
    r = evaluate_dimension(rows, DIMS[0], 0.40, 0.80)
    assert r["precision_defined"] and r["pass_precision"] >= 0.80
    assert "kappa_below_threshold" in r["reasons"]
    assert r["validated"] is False

def test_precision_below_threshold():
    rows = _rows({d: PREC_FAIL for d in DIMS})
    r = evaluate_dimension(rows, DIMS[0], 0.40, 0.80)
    assert "precision_below_threshold" in r["reasons"]
    assert r["validated"] is False


# --------------------------------------------------------------------------- #
# decide() — one dimension failing each criterion
# --------------------------------------------------------------------------- #

def test_decide_partitions_validated_and_excluded():
    patterns = {d: PASS for d in DIMS}
    patterns[DIMS[1]] = KAPPA_FAIL       # fails kappa
    patterns[DIMS[2]] = PREC_FAIL        # fails precision
    result = decide(_rows(patterns), 0.40, 0.80)

    assert DIMS[1] in result["excluded"]
    assert DIMS[2] in result["excluded"]
    assert DIMS[0] in result["validated"]
    assert set(result["validated"]) | set(result["excluded"]) == set(DIMS)
    assert result["rule"] == {"min_kappa": 0.40, "min_pass_precision": 0.80}
    assert "kappa_below_threshold" in result["dimensions"][DIMS[1]]["reasons"]
    assert "precision_below_threshold" in result["dimensions"][DIMS[2]]["reasons"]
