from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claude_behavior_eval.optimize import calculate_metrics
from claude_behavior_eval.schemas import MRBenchEvaluation

_DIMENSION_NAMES = list(MRBenchEvaluation.model_fields.keys())

_METRIC_ORDER = (
    ["deterministic_pass_rate"]
    + [f"{dim}_pass_rate" for dim in _DIMENSION_NAMES]
    + ["judge_macro_pass_rate"]
)


def _objective_marker(metric: str, objective_dims: list[str]) -> str:
    """Marker for the 'In objective' column: ✓/— for dimension rows, blank otherwise."""
    if metric.endswith("_pass_rate"):
        dim = metric[: -len("_pass_rate")]
        if dim in _DIMENSION_NAMES:
            return "✓" if dim in objective_dims else "—"
    return ""


def generate_markdown_report(
    baseline_metrics: dict[str, float],
    optimized_metrics: dict[str, float],
    objective_dims: list[str] | None = None,
) -> str:
    for metric in _METRIC_ORDER:
        if metric not in baseline_metrics:
            raise ValueError(f"Required metric '{metric}' is missing from baseline metrics.")
        if metric not in optimized_metrics:
            raise ValueError(f"Required metric '{metric}' is missing from optimized metrics.")

    # All eight dimensions are always reported. When objective_dims is provided, an
    # extra "In objective" column marks which dimensions the optimizer targeted.
    if objective_dims is None:
        lines = [
            "| Metric | Baseline | Optimized | Delta (pts) |",
            "|---|---|---|---|",
        ]
    else:
        lines = [
            "| Metric | Baseline | Optimized | Delta (pts) | In objective |",
            "|---|---|---|---|---|",
        ]

    for metric in _METRIC_ORDER:
        baseline_val = baseline_metrics[metric]
        optimized_val = optimized_metrics[metric]
        delta = optimized_val - baseline_val
        row = f"| {metric} | {baseline_val:.1f}% | {optimized_val:.1f}% | {delta:+.1f} |"
        if objective_dims is not None:
            row += f" {_objective_marker(metric, objective_dims)} |"
        lines.append(row)

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown comparison report for two evaluation JSONL result files."
    )
    parser.add_argument("--baseline-jsonl", required=True, help="Path to baseline JSONL results.")
    parser.add_argument("--optimized-jsonl", required=True, help="Path to optimized JSONL results.")
    parser.add_argument("--output-md", default=None, help="Path to write the Markdown report.")
    parser.add_argument(
        "--objective-dims-file", default=None,
        help="Optional judge_validated_dimensions.json; adds an 'In objective' column "
             "marking which dimensions were in the optimization objective (all 8 still shown).",
    )

    args = parser.parse_args()

    # report.py always reports all eight dimensions; the objective file only adds a marker.
    baseline_metrics = calculate_metrics(Path(args.baseline_jsonl))
    optimized_metrics = calculate_metrics(Path(args.optimized_jsonl))

    objective_dims = None
    if args.objective_dims_file is not None:
        spec = json.loads(Path(args.objective_dims_file).read_text(encoding="utf-8"))
        objective_dims = list(spec.get("validated", []))

    report = generate_markdown_report(baseline_metrics, optimized_metrics, objective_dims)

    if args.output_md is not None:
        output_path = Path(args.output_md)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
