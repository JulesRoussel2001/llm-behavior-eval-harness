"""
Pre-registered judge-validation rule as code. Local, no API calls.

Recomputes, per rubric dimension, Cohen's kappa and pass-precision from a
validate_judge results JSONL, applies the pre-registered rule, and writes
judge_validated_dimensions.json — the single source of truth for which dimensions
the optimizer objective may use.

Rule (defaults; both are CLI flags):
    kappa >= 0.40  AND  pass-precision >= 0.80

Positive class is pass=True, so pass_precision = TP / (TP + FP).

Undefined cases (reported explicitly, and treated as FAILING validation):
  - TP + FP == 0  -> pass-precision undefined -> dimension FAILS.
  - expected agreement == 1 (pe == 1) -> Cohen's kappa undefined -> dimension FAILS.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/08_judge_decision.py \
    --input judge_dev_results.jsonl \
    --min-kappa 0.40 --min-pass-precision 0.80 \
    --output judge_validated_dimensions.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from claude_behavior_eval.schemas import MRBenchEvaluation

DIMS = list(MRBenchEvaluation.model_fields.keys())


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def confusion(rows: list[dict], dim: str) -> tuple[int, int, int, int]:
    tp = fp = fn = tn = 0
    for r in rows:
        h = bool(r["human_labels"][dim])
        j = bool(r["judge_labels"][dim])
        if h and j:
            tp += 1
        elif (not h) and j:
            fp += 1
        elif h and (not j):
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def cohen_kappa(tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Cohen's kappa, or None if expected agreement == 1 (undefined)."""
    n = tp + fp + fn + tn
    if n == 0:
        return None
    po = (tp + tn) / n
    pe = ((tp + fp) / n) * ((tp + fn) / n) + ((fn + tn) / n) * ((fp + tn) / n)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def pass_precision(tp: int, fp: int) -> float | None:
    """Precision of pass=True predictions, or None if TP+FP == 0 (undefined)."""
    if tp + fp == 0:
        return None
    return tp / (tp + fp)


def evaluate_dimension(
    rows: list[dict], dim: str, min_kappa: float, min_pass_precision: float
) -> dict:
    tp, fp, fn, tn = confusion(rows, dim)
    kappa = cohen_kappa(tp, fp, fn, tn)
    precision = pass_precision(tp, fp)

    reasons: list[str] = []
    if kappa is None:
        reasons.append("kappa_undefined")
    elif kappa < min_kappa:
        reasons.append("kappa_below_threshold")
    if precision is None:
        reasons.append("precision_undefined")
    elif precision < min_pass_precision:
        reasons.append("precision_below_threshold")

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "kappa": kappa,
        "kappa_defined": kappa is not None,
        "pass_precision": precision,
        "precision_defined": precision is not None,
        "validated": not reasons,
        "reasons": reasons,
    }


def decide(rows: list[dict], min_kappa: float, min_pass_precision: float) -> dict:
    dimensions = {
        dim: evaluate_dimension(rows, dim, min_kappa, min_pass_precision)
        for dim in DIMS
    }
    validated = [d for d in DIMS if dimensions[d]["validated"]]
    excluded = [d for d in DIMS if not dimensions[d]["validated"]]
    return {
        "rule": {"min_kappa": min_kappa, "min_pass_precision": min_pass_precision},
        "validated": validated,
        "excluded": excluded,
        "dimensions": dimensions,
    }


def sha256_of_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the pre-registered judge-validation rule.")
    parser.add_argument("--input", required=True, help="validate_judge results JSONL (recomputed from).")
    parser.add_argument("--min-kappa", type=float, default=0.40)
    parser.add_argument("--min-pass-precision", type=float, default=0.80)
    parser.add_argument("--output", default="judge_validated_dimensions.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    rows = read_jsonl(input_path)
    result = decide(rows, args.min_kappa, args.min_pass_precision)
    result["source"] = str(input_path)
    result["sha256_of_source"] = sha256_of_file(input_path)

    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Rule: kappa >= {args.min_kappa} AND pass-precision >= {args.min_pass_precision}")
    print(f"Source: {input_path} (sha256={result['sha256_of_source'][:12]}...)")
    for dim in DIMS:
        d = result["dimensions"][dim]
        k = "undef" if d["kappa"] is None else f"{d['kappa']:.2f}"
        p = "undef" if d["pass_precision"] is None else f"{d['pass_precision']:.2f}"
        status = "VALIDATED" if d["validated"] else "EXCLUDED (" + ", ".join(d["reasons"]) + ")"
        print(f"  {dim:<30} kappa={k:<6} pass_prec={p:<6} {status}")
    print(f"\nValidated ({len(result['validated'])}): {result['validated']}")
    print(f"Excluded  ({len(result['excluded'])}): {result['excluded']}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
