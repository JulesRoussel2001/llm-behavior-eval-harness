from __future__ import annotations

import argparse
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


def generate_markdown_report(
    baseline_metrics: dict[str, float],
    optimized_metrics: dict[str, float],
) -> str:
    for metric in _METRIC_ORDER:
        if metric not in baseline_metrics:
            raise ValueError(f"Required metric '{metric}' is missing from baseline metrics.")
        if metric not in optimized_metrics:
            raise ValueError(f"Required metric '{metric}' is missing from optimized metrics.")

    lines = [
        "| Metric | Baseline | Optimized | Delta (pts) |",
        "|---|---|---|---|",
    ]
    for metric in _METRIC_ORDER:
        baseline_val = baseline_metrics[metric]
        optimized_val = optimized_metrics[metric]
        delta = optimized_val - baseline_val
        lines.append(
            f"| {metric} | {baseline_val:.1f}% | {optimized_val:.1f}% | {delta:+.1f} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown comparison report for two evaluation JSONL result files."
    )
    parser.add_argument("--baseline-jsonl", required=True, help="Path to baseline JSONL results.")
    parser.add_argument("--optimized-jsonl", required=True, help="Path to optimized JSONL results.")
    parser.add_argument("--output-md", default=None, help="Path to write the Markdown report.")

    args = parser.parse_args()

    baseline_metrics = calculate_metrics(Path(args.baseline_jsonl))
    optimized_metrics = calculate_metrics(Path(args.optimized_jsonl))

    report = generate_markdown_report(baseline_metrics, optimized_metrics)

    if args.output_md is not None:
        output_path = Path(args.output_md)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
