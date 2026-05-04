from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from claude_behavior_eval.judge import ClaudeRubricJudge
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

_JUDGE_DIMENSIONS = list(MRBenchEvaluation.model_fields.keys())
_EXCERPT_LENGTH = 120

_TRUE_LABELS = {"Yes", "yes", "TRUE", "true", "1"}
_FALSE_LABELS = {"No", "no", "FALSE", "false", "0"}


def parse_human_label(value: str) -> bool:
    normalized = value.strip()
    if normalized in _TRUE_LABELS:
        return True
    if normalized in _FALSE_LABELS:
        return False
    raise ValueError(f"Unknown human label: {value!r}")


def compute_binary_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, float]:
    n = len(y_true)
    if n == 0:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)

    accuracy = (tp + tn) / n * 100.0
    precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


# Each entry: (human_val, judge_val, item_id, judge_reason, tutor_response_excerpt)
_DimEntry = tuple[bool, bool, str, str, str]


def validate_judge(
    input_csv: Path,
    output_jsonl: Path,
    report_md: Path,
    judge: ClaudeRubricJudge | None = None,
) -> dict[str, object]:
    if judge is None:
        judge = ClaudeRubricJudge()

    jsonl_rows: list[dict] = []
    dim_data: dict[str, list[_DimEntry]] = {dim: [] for dim in _JUDGE_DIMENSIONS}

    with input_csv.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            item_id = row["id"]

            raw_constraints = row.get("instruction_constraints", "").strip()
            instruction_constraints = json.loads(raw_constraints) if raw_constraints else []

            raw_rubric = row.get("expected_rubric", "").strip()
            expected_rubric = json.loads(raw_rubric) if raw_rubric else {}

            item = DatasetItem(
                id=item_id,
                student_question=row["student_question"],
                target_learner_level=row["target_learner_level"],
                instruction_constraints=instruction_constraints,
                expected_rubric=expected_rubric,
            )

            tutor_response = row["tutor_response"]
            evaluation = judge.evaluate_response(item, tutor_response)
            excerpt = tutor_response[:_EXCERPT_LENGTH]

            human_labels: dict[str, bool] = {}
            judge_labels: dict[str, bool] = {}
            judge_reasons: dict[str, str] = {}
            matches: dict[str, bool] = {}

            for dim in _JUDGE_DIMENSIONS:
                human_val = parse_human_label(row[f"human_{dim}"])
                judgment = getattr(evaluation, dim)
                judge_val: bool = judgment.passed
                reason: str = judgment.reason

                human_labels[dim] = human_val
                judge_labels[dim] = judge_val
                judge_reasons[dim] = reason
                matches[dim] = human_val == judge_val

                dim_data[dim].append((human_val, judge_val, item_id, reason, excerpt))

            jsonl_rows.append({
                "item_id": item_id,
                "human_labels": human_labels,
                "judge_labels": judge_labels,
                "judge_reasons": judge_reasons,
                "matches": matches,
                "tutor_response_excerpt": excerpt,
            })

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in jsonl_rows:
            f.write(json.dumps(row) + "\n")

    per_dimension: dict[str, dict[str, float]] = {}
    for dim in _JUDGE_DIMENSIONS:
        entries = dim_data[dim]
        per_dimension[dim] = compute_binary_metrics(
            [e[0] for e in entries],
            [e[1] for e in entries],
        )

    macro_f1 = sum(per_dimension[dim]["f1"] for dim in _JUDGE_DIMENSIONS) / len(_JUDGE_DIMENSIONS)
    macro_accuracy = sum(per_dimension[dim]["accuracy"] for dim in _JUDGE_DIMENSIONS) / len(_JUDGE_DIMENSIONS)

    metrics: dict[str, object] = {
        "macro_f1": macro_f1,
        "macro_accuracy": macro_accuracy,
        "per_dimension": per_dimension,
    }

    _write_report(report_md, metrics, dim_data)

    print("Judge Reliability Report")
    print(f"  Macro F1:       {macro_f1:.1f}%")
    print(f"  Macro Accuracy: {macro_accuracy:.1f}%")
    print("  Per-dimension F1:")
    for dim in _JUDGE_DIMENSIONS:
        print(f"    {dim}: {per_dimension[dim]['f1']:.1f}%")

    return metrics


def _write_report(
    report_md: Path,
    metrics: dict[str, object],
    dim_data: dict[str, list[_DimEntry]],
) -> None:
    macro_f1: float = metrics["macro_f1"]  # type: ignore[assignment]
    macro_accuracy: float = metrics["macro_accuracy"]  # type: ignore[assignment]
    per_dimension: dict[str, dict[str, float]] = metrics["per_dimension"]  # type: ignore[assignment]

    lines: list[str] = [
        "# Judge Validation Report",
        "",
        f"**Macro F1:** {macro_f1:.1f}%  ",
        f"**Macro Accuracy:** {macro_accuracy:.1f}%",
        "",
        "## Dimension Metrics",
        "",
        "| Dimension | Accuracy | Precision | Recall | F1 |",
        "|---|---|---|---|---|",
    ]

    for dim in _JUDGE_DIMENSIONS:
        m = per_dimension[dim]
        lines.append(
            f"| {dim} | {m['accuracy']:.1f}% | {m['precision']:.1f}% "
            f"| {m['recall']:.1f}% | {m['f1']:.1f}% |"
        )

    lines += ["", "## Weakest Dimensions", ""]

    sorted_dims = sorted(_JUDGE_DIMENSIONS, key=lambda d: per_dimension[d]["f1"])

    for dim in sorted_dims:
        f1 = per_dimension[dim]["f1"]
        lines.append(f"### {dim} (F1: {f1:.1f}%)")
        lines.append("")

        disagreements = [
            (item_id, human, judge_val, reason, excerpt)
            for (human, judge_val, item_id, reason, excerpt) in dim_data[dim]
            if human != judge_val
        ]

        if not disagreements:
            lines.append("No disagreements.")
            lines.append("")
            continue

        for item_id, human, judge_val, reason, excerpt in disagreements[:3]:
            lines += [
                f"- **Item:** {item_id}",
                f"  - **Human:** {human}",
                f"  - **Judge:** {judge_val}",
                f"  - **Reason:** {reason}",
                f"  - **Excerpt:** {excerpt!r}",
                "",
            ]

    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate ClaudeRubricJudge alignment against MRBench human annotations."
    )
    parser.add_argument("--input-csv", required=True, help="Path to validation CSV.")
    parser.add_argument(
        "--output-jsonl", default="judge_validation_results.jsonl",
        help="Path to write per-row JSONL results.",
    )
    parser.add_argument(
        "--report-md", default="judge_validation_report.md",
        help="Path to write the Markdown report.",
    )

    args = parser.parse_args()

    validate_judge(
        input_csv=Path(args.input_csv),
        output_jsonl=Path(args.output_jsonl),
        report_md=Path(args.report_md),
    )


if __name__ == "__main__":
    main()
